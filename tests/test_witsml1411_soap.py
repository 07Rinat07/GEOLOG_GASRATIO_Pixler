from __future__ import annotations

from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
import json
import threading
import xml.etree.ElementTree as ET

import numpy as np
import pytest

from geoworkbench.importers.witsml1411 import (
    Witsml1411ConnectionProfile,
    Witsml1411Credentials,
    Witsml1411HttpRequest,
    Witsml1411HttpResponse,
    Witsml1411ReadOnlyService,
    Witsml1411RetryPolicy,
    Witsml1411ServerError,
    Witsml1411SoapClient,
    Witsml1411TransportError,
    UrllibWitsml1411HttpTransport,
)
from geoworkbench.services.witsml1411_audit import (
    InMemoryWitsml1411AuditSink,
    JsonlWitsml1411AuditSink,
)
from geoworkbench.services.witsml1411_profiles import Witsml1411ProfileStore
from geoworkbench.services.witsml_credentials import InMemoryWitsmlCredentialStore
from geoworkbench.services.witsml_import_review import WitsmlImportReviewController


SOAP = "http://schemas.xmlsoap.org/soap/envelope/"
MSG = "http://www.witsml.org/message/120"
SCHEMA = "http://www.witsml.org/schemas/1series"


def _soap_response(operation: str, **values: str) -> bytes:
    envelope = ET.Element(f"{{{SOAP}}}Envelope")
    body = ET.SubElement(envelope, f"{{{SOAP}}}Body")
    response = ET.SubElement(body, f"{{{MSG}}}{operation}Response")
    for name, value in values.items():
        ET.SubElement(response, name).text = value
    return ET.tostring(envelope, encoding="utf-8", xml_declaration=True)


class ScriptedTransport:
    def __init__(self, script):
        self.script = list(script)
        self.requests = []

    def send(self, request):
        self.requests.append(request)
        item = self.script.pop(0)
        if isinstance(item, Exception):
            raise item
        return item


def _profile(tmp_path: Path | None = None) -> Witsml1411ConnectionProfile:
    return Witsml1411ConnectionProfile(
        profile_id="test",
        name="Test Store",
        endpoint="https://witsml.example.test/store",
        username="operator",
        credential_id="cred-test",
        timeout_seconds=3,
        retry=Witsml1411RetryPolicy(max_attempts=3, backoff_seconds=0, max_backoff_seconds=0),
    )


def test_get_version_builds_soap_action_and_basic_auth() -> None:
    transport = ScriptedTransport([
        Witsml1411HttpResponse(200, {}, _soap_response("WMLS_GetVersion", Result="1.3.1.1,1.4.1.1"))
    ])
    client = Witsml1411SoapClient(
        _profile(),
        Witsml1411Credentials("operator", "secret"),
        transport=transport,
    )

    assert client.get_version() == ("1.3.1.1", "1.4.1.1")
    request = transport.requests[0]
    assert request.headers["SOAPAction"] == '"http://www.witsml.org/action/120/Store.WMLS_GetVersion"'
    assert request.headers["Authorization"].startswith("Basic ")
    assert b"secret" not in request.body
    assert b"WMLS_GetVersion" in request.body


def test_remote_profiles_require_verified_https() -> None:
    with pytest.raises(ValueError, match="must use HTTPS"):
        Witsml1411ConnectionProfile("remote-http", "Remote", "http://store.example.test")
    with pytest.raises(ValueError, match="localhost"):
        Witsml1411ConnectionProfile(
            "remote-unverified",
            "Remote",
            "https://store.example.test",
            verify_tls=False,
        )

    local = Witsml1411ConnectionProfile(
        "local-dev",
        "Local development store",
        "http://127.0.0.1:8080/store",
    )
    assert local.endpoint.startswith("http://127.0.0.1")


def test_profile_endpoint_rejects_embedded_credentials_and_fragments() -> None:
    with pytest.raises(ValueError, match="Credentials must not be embedded"):
        Witsml1411ConnectionProfile(
            "embedded-secret",
            "Unsafe",
            "https://operator:secret@store.example.test/witsml",
        )
    with pytest.raises(ValueError, match="must not contain a URL fragment"):
        Witsml1411ConnectionProfile(
            "fragment",
            "Unsafe",
            "https://store.example.test/witsml#credential",
        )


def test_urllib_transport_rejects_redirects_before_forwarding_credentials() -> None:
    class RedirectHandler(BaseHTTPRequestHandler):
        followed = False
        post_bodies: list[bytes] = []
        redirected_authorizations: list[str | None] = []

        def do_POST(self) -> None:  # noqa: N802 - stdlib handler contract
            content_length = int(self.headers.get("Content-Length", "0"))
            type(self).post_bodies.append(self.rfile.read(content_length))
            self.send_response(302)
            self.send_header("Location", "/redirected")
            self.send_header("Content-Length", "0")
            self.send_header("Connection", "close")
            self.end_headers()
            self.wfile.flush()
            self.close_connection = True

        def do_GET(self) -> None:  # noqa: N802 - stdlib handler contract
            type(self).followed = True
            type(self).redirected_authorizations.append(
                self.headers.get("Authorization")
            )
            self.send_response(200)
            self.send_header("Content-Length", "0")
            self.send_header("Connection", "close")
            self.end_headers()
            self.wfile.flush()
            self.close_connection = True

        def log_message(self, _format: str, *_args: object) -> None:
            return

    server = ThreadingHTTPServer(("127.0.0.1", 0), RedirectHandler)
    worker = threading.Thread(target=server.serve_forever, daemon=True)
    worker.start()
    try:
        endpoint = f"http://127.0.0.1:{server.server_port}/store"
        request = Witsml1411HttpRequest(
            endpoint=endpoint,
            soap_action="test",
            body=b"<soap/>",
            headers={"Authorization": "Basic must-not-be-forwarded"},
            timeout_seconds=2.0,
            verify_tls=True,
            max_response_bytes=4096,
        )
        with pytest.raises(Witsml1411TransportError, match="HTTP 302"):
            UrllibWitsml1411HttpTransport().send(request)
        assert RedirectHandler.post_bodies == [b"<soap/>"]
        assert RedirectHandler.followed is False
        assert RedirectHandler.redirected_authorizations == []
    finally:
        server.shutdown()
        worker.join(timeout=2.0)
        server.server_close()


def test_retry_is_applied_only_to_retryable_transport_failures() -> None:
    audit = InMemoryWitsml1411AuditSink()
    transport = ScriptedTransport([
        Witsml1411TransportError("temporary", status=503, retryable=True),
        Witsml1411HttpResponse(200, {}, _soap_response("WMLS_GetVersion", Result="1.4.1.1")),
    ])
    client = Witsml1411SoapClient(_profile(), transport=transport, audit=audit, sleep=lambda _v: None)

    assert client.get_version() == ("1.4.1.1",)
    assert len(transport.requests) == 2
    assert [item.outcome for item in audit.events] == ["retry", "success"]


def test_negative_witsml_result_is_not_retried() -> None:
    transport = ScriptedTransport([
        Witsml1411HttpResponse(
            200,
            {},
            _soap_response(
                "WMLS_GetFromStore",
                Result="-401",
                XMLout="",
                SuppMsgOut="Object not supported",
            ),
        )
    ])
    client = Witsml1411SoapClient(_profile(), transport=transport)

    with pytest.raises(Witsml1411ServerError, match="-401"):
        client.get_from_store("well", '<wells xmlns="http://www.witsml.org/schemas/1series"/>')
    assert len(transport.requests) == 1


def test_hierarchy_logdata_and_import_review_reuse() -> None:
    cap_xml = f'''<capServers xmlns="{SCHEMA}" version="1.4.1.1"><capServer>
      <description>Test store</description><vendor>Vendor</vendor>
      <function name="WMLS_GetFromStore"/><dataObject>well</dataObject>
      <dataObject>wellbore</dataObject><dataObject>log</dataObject>
    </capServer></capServers>'''
    wells_xml = f'''<wells xmlns="{SCHEMA}" version="1.4.1.1">
      <well uid="w1"><name>Well A</name><field>Field</field></well></wells>'''
    wellbores_xml = f'''<wellbores xmlns="{SCHEMA}" version="1.4.1.1">
      <wellbore uid="wb1" uidWell="w1"><nameWell>Well A</nameWell><name>Main</name></wellbore>
    </wellbores>'''
    logs_xml = f'''<logs xmlns="{SCHEMA}" version="1.4.1.1">
      <log uid="log1" uidWell="w1" uidWellbore="wb1"><nameWell>Well A</nameWell>
      <nameWellbore>Main</nameWellbore><name>Drilling</name><indexType>measured depth</indexType>
      <indexCurve>DEPT</indexCurve><direction>increasing</direction>
      <logCurveInfo uid="dept"><mnemonic>DEPT</mnemonic><unit>m</unit><typeLogData>double</typeLogData></logCurveInfo>
      <logCurveInfo uid="rop"><mnemonic>ROP</mnemonic><unit>ft/h</unit><curveDescription>Rate of penetration</curveDescription><typeLogData>double</typeLogData><nullValue>-999.25</nullValue></logCurveInfo>
      </log></logs>'''
    data_xml = logs_xml.replace(
        "</log></logs>",
        "<logData><mnemonicList>DEPT,ROP</mnemonicList><unitList>m,ft/h</unitList>"
        "<data>1000,32.80839895</data><data>1000.5,-999.25</data>"
        "</logData></log></logs>",
    )
    script = [
        Witsml1411HttpResponse(200, {}, _soap_response("WMLS_GetVersion", Result="1.4.1.1")),
        Witsml1411HttpResponse(200, {}, _soap_response("WMLS_GetCap", Result="1", CapabilitiesOut=cap_xml, SuppMsgOut="")),
        Witsml1411HttpResponse(200, {}, _soap_response("WMLS_GetFromStore", Result="1", XMLout=wells_xml, SuppMsgOut="")),
        Witsml1411HttpResponse(200, {}, _soap_response("WMLS_GetFromStore", Result="1", XMLout=wellbores_xml, SuppMsgOut="")),
        Witsml1411HttpResponse(200, {}, _soap_response("WMLS_GetFromStore", Result="1", XMLout=logs_xml, SuppMsgOut="")),
        Witsml1411HttpResponse(200, {}, _soap_response("WMLS_GetFromStore", Result="1", XMLout=data_xml, SuppMsgOut="")),
    ]
    service = Witsml1411ReadOnlyService(Witsml1411SoapClient(_profile(), transport=ScriptedTransport(script)))

    handshake = service.handshake()
    assert handshake.selected_version == "1.4.1.1"
    assert handshake.capabilities.supports_get_from_store
    well = service.list_wells()[0]
    wellbore = service.list_wellbores(well.uid)[0]
    log = service.list_logs(well.uid, wellbore.uid)[0]
    channel_set = service.fetch_log_channel_set(log)

    assert channel_set.title == "Drilling"
    assert channel_set.indexes[0].mnemonic == "DEPT"
    assert channel_set.rows[0].index_values == (1000.0,)
    assert channel_set.rows[1].channel_values == (None,)

    controller = WitsmlImportReviewController()
    commit = controller.commit(channel_set, controller.initial_plan(channel_set))
    np.testing.assert_allclose(commit.dataset.active_index.values, [1000.0, 1000.5])
    rop = commit.dataset.curve_by_mnemonic("ROP")
    assert rop.metadata.unit == "m/h"
    assert rop.values[0] == pytest.approx(10.0)
    assert np.isnan(rop.values[1])
    assert commit.dataset.parameters["WITSML_SCHEMA_VERSION"] == "1.4.1.1"


def test_profile_store_and_credentials_never_serialize_password(tmp_path: Path) -> None:
    profile_path = tmp_path / "profiles.json"
    store = Witsml1411ProfileStore(profile_path)
    profile = _profile()
    store.upsert(profile)
    credential_store = InMemoryWitsmlCredentialStore()
    credential_store.save(profile.credential_id or "", Witsml1411Credentials("operator", "top-secret"))

    text = profile_path.read_text(encoding="utf-8")
    assert "top-secret" not in text
    assert "password" not in text.casefold()
    assert store.load_all() == (profile,)
    assert credential_store.load("cred-test").password == "top-secret"


def test_hash_chained_audit_redacts_endpoint_userinfo_and_does_not_store_password(tmp_path: Path) -> None:
    audit_path = tmp_path / "audit.jsonl"
    sink = JsonlWitsml1411AuditSink(audit_path, fsync=False)
    transport = ScriptedTransport([
        Witsml1411HttpResponse(200, {}, _soap_response("WMLS_GetVersion", Result="1.4.1.1"))
    ])
    client = Witsml1411SoapClient(
        _profile(),
        Witsml1411Credentials("operator", "audit-secret"),
        transport=transport,
        audit=sink,
    )
    client.get_version()

    line = audit_path.read_text(encoding="utf-8")
    payload = json.loads(line)
    assert payload["sequence"] == 1
    assert len(payload["entry_hash"]) == 64
    assert "audit-secret" not in line
    assert "Authorization" not in line
    assert payload["endpoint"] == "https://witsml.example.test/store"


def test_read_only_client_rejects_mutating_operation() -> None:
    client = Witsml1411SoapClient(_profile(), transport=ScriptedTransport([]))
    with pytest.raises(ValueError, match="not permitted"):
        client._invoke("WMLS_AddToStore", {})  # noqa: SLF001 - security contract


def test_soap_dtd_is_rejected_without_retry() -> None:
    payload = b'''<?xml version="1.0"?><!DOCTYPE x [<!ENTITY a "boom">]>
    <soap:Envelope xmlns:soap="http://schemas.xmlsoap.org/soap/envelope/"><soap:Body/></soap:Envelope>'''
    transport = ScriptedTransport([Witsml1411HttpResponse(200, {}, payload)])
    client = Witsml1411SoapClient(_profile(), transport=transport)
    with pytest.raises(Exception, match="forbidden"):
        client.get_version()
    assert len(transport.requests) == 1


def test_soap_dtd_is_rejected_even_after_a_long_xml_preamble() -> None:
    payload = (
        b" " * 9_000
        + b'''<!DOCTYPE x [<!ENTITY a "expanded">]>
    <soap:Envelope xmlns:soap="http://schemas.xmlsoap.org/soap/envelope/">
      <soap:Body><WMLS_GetVersionResponse><Result>&a;</Result></WMLS_GetVersionResponse></soap:Body>
    </soap:Envelope>'''
    )
    transport = ScriptedTransport([Witsml1411HttpResponse(200, {}, payload)])
    client = Witsml1411SoapClient(_profile(), transport=transport)

    with pytest.raises(Exception, match="forbidden"):
        client.get_version()
    assert len(transport.requests) == 1


def test_witsml1411_ui_and_project_contract_are_wired() -> None:
    root = Path("src/geoworkbench")
    dialog = (root / "ui" / "witsml1411_dialog.py").read_text(encoding="utf-8")
    main = (root / "ui" / "main_window.py").read_text(encoding="utf-8")
    import_dialog = (root / "ui" / "witsml_import_dialog.py").read_text(encoding="utf-8")

    assert "Witsml1411ReadOnlyService" in dialog
    assert "Windows Credential Manager" in dialog or "witsml1411.remember" in dialog
    assert "package: WitsmlDataPackage | None = None" in import_dialog
    assert "open_witsml1411_store" in main
    assert "WitsmlProjectImportController" in main


def test_audit_hash_chain_detects_tampering(tmp_path: Path) -> None:
    audit_path = tmp_path / "audit.jsonl"
    sink = JsonlWitsml1411AuditSink(audit_path, fsync=False)
    transport = ScriptedTransport([
        Witsml1411HttpResponse(200, {}, _soap_response("WMLS_GetVersion", Result="1.4.1.1"))
    ])
    Witsml1411SoapClient(_profile(), transport=transport, audit=sink).get_version()
    assert sink.verify()[0] == 1

    text = audit_path.read_text(encoding="utf-8").replace('"outcome": "success"', '"outcome": "error"')
    audit_path.write_text(text, encoding="utf-8")
    with pytest.raises(ValueError, match="hash chain"):
        JsonlWitsml1411AuditSink(audit_path, fsync=False)
