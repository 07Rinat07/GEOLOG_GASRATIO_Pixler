from __future__ import annotations

from base64 import b64encode
from dataclasses import dataclass
from datetime import datetime, timezone
import socket
import ssl
import time
from typing import Mapping, Protocol
from urllib import error as urlerror
from urllib import request as urlrequest
from urllib.parse import urlsplit
from uuid import uuid4
import xml.etree.ElementTree as ET

from geoworkbench.importers.witsml1411.models import (
    Witsml1411AuditEvent,
    Witsml1411AuthMode,
    Witsml1411ConnectionProfile,
    Witsml1411Credentials,
)
from geoworkbench.services.witsml1411_audit import (
    InMemoryWitsml1411AuditSink,
    Witsml1411AuditSink,
    sanitize_endpoint,
)


SOAP_ENV = "http://schemas.xmlsoap.org/soap/envelope/"
SOAP_ENC = "http://schemas.xmlsoap.org/soap/encoding/"
XSI = "http://www.w3.org/2001/XMLSchema-instance"
XSD = "http://www.w3.org/2001/XMLSchema"
WITSML_MESSAGE = "http://www.witsml.org/message/120"
WITSML_ACTION = "http://www.witsml.org/action/120/Store."
_FORBIDDEN_XML = (b"<!doctype", b"<!entity")

for prefix, namespace in (
    ("soap", SOAP_ENV),
    ("soapenc", SOAP_ENC),
    ("xsi", XSI),
    ("xsd", XSD),
    ("wits", WITSML_MESSAGE),
):
    ET.register_namespace(prefix, namespace)


class Witsml1411Error(RuntimeError):
    pass


class Witsml1411TransportError(Witsml1411Error):
    def __init__(self, message: str, *, status: int | None = None, retryable: bool = False) -> None:
        super().__init__(message)
        self.status = status
        self.retryable = retryable


class Witsml1411SoapFault(Witsml1411Error):
    def __init__(self, fault_code: str | None, fault_string: str | None) -> None:
        self.fault_code = fault_code
        self.fault_string = fault_string
        super().__init__(f"SOAP fault {fault_code or 'unknown'}: {fault_string or 'no message'}")


class Witsml1411ServerError(Witsml1411Error):
    def __init__(self, operation: str, result: int, supplementary_message: str | None) -> None:
        self.operation = operation
        self.result = result
        self.supplementary_message = supplementary_message
        super().__init__(
            f"{operation} failed with WITSML result {result}: "
            f"{supplementary_message or 'no supplementary message'}"
        )


@dataclass(frozen=True, slots=True)
class Witsml1411HttpRequest:
    endpoint: str
    soap_action: str
    body: bytes
    headers: Mapping[str, str]
    timeout_seconds: float
    verify_tls: bool
    max_response_bytes: int


@dataclass(frozen=True, slots=True)
class Witsml1411HttpResponse:
    status: int
    headers: Mapping[str, str]
    body: bytes


class Witsml1411HttpTransport(Protocol):
    def send(self, request: Witsml1411HttpRequest) -> Witsml1411HttpResponse: ...


class UrllibWitsml1411HttpTransport:
    def send(self, request: Witsml1411HttpRequest) -> Witsml1411HttpResponse:
        context = None
        if request.endpoint.casefold().startswith("https://"):
            context = ssl.create_default_context()
            if not request.verify_tls:
                context.check_hostname = False
                context.verify_mode = ssl.CERT_NONE
        http_request = urlrequest.Request(
            request.endpoint,
            data=request.body,
            method="POST",
            headers=dict(request.headers),
        )
        try:
            with urlrequest.urlopen(
                http_request,
                timeout=request.timeout_seconds,
                context=context,
            ) as response:
                payload = response.read(request.max_response_bytes + 1)
                if len(payload) > request.max_response_bytes:
                    raise Witsml1411TransportError("SOAP response exceeds configured size limit")
                return Witsml1411HttpResponse(
                    status=int(response.status),
                    headers=dict(response.headers.items()),
                    body=payload,
                )
        except urlerror.HTTPError as exc:
            payload = exc.read(request.max_response_bytes + 1)
            if len(payload) > request.max_response_bytes:
                payload = payload[: request.max_response_bytes]
            if exc.code == 500 and payload:
                # SOAP 1.1 faults are commonly returned as HTTP 500 and must be parsed.
                return Witsml1411HttpResponse(exc.code, dict(exc.headers.items()), payload)
            raise Witsml1411TransportError(
                f"HTTP {exc.code}: {exc.reason}",
                status=exc.code,
                retryable=exc.code in {408, 425, 429, 500, 502, 503, 504},
            ) from exc
        except (urlerror.URLError, TimeoutError, socket.timeout, ConnectionError) as exc:
            raise Witsml1411TransportError(str(exc), retryable=True) from exc


@dataclass(frozen=True, slots=True)
class _Invocation:
    operation: str
    values: Mapping[str, str]
    raw_response: bytes
    status: int
    request_id: str
    attempts: int
    duration_seconds: float


class Witsml1411SoapClient:
    """Read-only WITSML Store SOAP client for API/data version 1.4.1.1."""

    _READ_ONLY_OPERATIONS = frozenset({"WMLS_GetVersion", "WMLS_GetCap", "WMLS_GetFromStore"})

    def __init__(
        self,
        profile: Witsml1411ConnectionProfile,
        credentials: Witsml1411Credentials | None = None,
        *,
        transport: Witsml1411HttpTransport | None = None,
        audit: Witsml1411AuditSink | None = None,
        sleep=time.sleep,
        monotonic=time.monotonic,
        max_response_bytes: int = 128 * 1024**2,
    ) -> None:
        parts = urlsplit(profile.endpoint)
        if parts.username or parts.password:
            raise ValueError("Credentials must not be embedded in the WITSML endpoint URL")
        if max_response_bytes < 1024:
            raise ValueError("max_response_bytes is too small")
        self.profile = profile
        self.credentials = credentials or Witsml1411Credentials(profile.username, "")
        self.transport = transport or UrllibWitsml1411HttpTransport()
        self.audit = audit or InMemoryWitsml1411AuditSink()
        self._sleep = sleep
        self._monotonic = monotonic
        self.max_response_bytes = max_response_bytes

    def get_version(self) -> tuple[str, ...]:
        invocation = self._invoke("WMLS_GetVersion", {})
        versions = tuple(item.strip() for item in invocation.values.get("Result", "").split(",") if item.strip())
        if not versions:
            raise Witsml1411Error("WMLS_GetVersion returned no data schema versions")
        return versions

    def get_capabilities(self, data_version: str | None = None) -> tuple[int, str, str | None]:
        version = (data_version or self.profile.data_version).strip()
        invocation = self._invoke("WMLS_GetCap", {"OptionsIn": f"dataVersion={version}"})
        result = _parse_result(invocation.values, "WMLS_GetCap")
        supplementary = invocation.values.get("SuppMsgOut") or None
        if result < 0:
            raise Witsml1411ServerError("WMLS_GetCap", result, supplementary)
        capabilities = invocation.values.get("CapabilitiesOut", "")
        if not capabilities.strip():
            raise Witsml1411Error("WMLS_GetCap returned empty CapabilitiesOut")
        return result, capabilities, supplementary

    def get_from_store(
        self,
        object_type: str,
        query_xml: str,
        *,
        options_in: str = "returnElements=requested",
        capabilities_in: str = "",
        selection: Mapping[str, str] | None = None,
    ) -> tuple[int, str, str | None]:
        token = object_type.strip()
        if not token or any(char in token for char in "<>\r\n\x00"):
            raise ValueError("Invalid WITSML object type")
        invocation = self._invoke(
            "WMLS_GetFromStore",
            {
                "WMLtypeIn": token,
                "QueryIn": query_xml,
                "OptionsIn": options_in,
                "CapabilitiesIn": capabilities_in,
            },
            object_type=token,
            selection=selection,
        )
        result = _parse_result(invocation.values, "WMLS_GetFromStore")
        supplementary = invocation.values.get("SuppMsgOut") or None
        if result < 0:
            raise Witsml1411ServerError("WMLS_GetFromStore", result, supplementary)
        return result, invocation.values.get("XMLout", ""), supplementary

    def _invoke(
        self,
        operation: str,
        arguments: Mapping[str, str],
        *,
        object_type: str | None = None,
        selection: Mapping[str, str] | None = None,
    ) -> _Invocation:
        if operation not in self._READ_ONLY_OPERATIONS:
            raise ValueError(f"Operation is not permitted by the read-only client: {operation}")
        body = _build_soap_envelope(operation, arguments)
        request_id = uuid4().hex
        started_all = self._monotonic()
        headers = {
            "Content-Type": "text/xml; charset=utf-8",
            "SOAPAction": f'"{WITSML_ACTION}{operation}"',
            "Accept": "text/xml, application/soap+xml",
            "User-Agent": "GEOLOG-GASRATIO-Pixler/WITSML1411-read-only",
            "X-Request-ID": request_id,
        }
        if self.profile.auth_mode is Witsml1411AuthMode.BASIC:
            raw = f"{self.credentials.username}:{self.credentials.password}".encode("utf-8")
            headers["Authorization"] = "Basic " + b64encode(raw).decode("ascii")
        last_error: Exception | None = None
        for attempt in range(1, self.profile.retry.max_attempts + 1):
            started = self._monotonic()
            response: Witsml1411HttpResponse | None = None
            try:
                response = self.transport.send(
                    Witsml1411HttpRequest(
                        endpoint=self.profile.endpoint,
                        soap_action=f"{WITSML_ACTION}{operation}",
                        body=body,
                        headers=headers,
                        timeout_seconds=self.profile.timeout_seconds,
                        verify_tls=self.profile.verify_tls,
                        max_response_bytes=self.max_response_bytes,
                    )
                )
                values = _parse_soap_response(response.body, operation)
                duration = self._monotonic() - started
                result = _optional_int(values.get("Result"))
                self.audit.record(
                    Witsml1411AuditEvent(
                        timestamp_utc=datetime.now(timezone.utc),
                        request_id=request_id,
                        operation=operation,
                        endpoint=sanitize_endpoint(self.profile.endpoint),
                        attempt=attempt,
                        outcome="success" if result is None or result >= 0 else "witsml-error",
                        duration_seconds=duration,
                        http_status=response.status,
                        witsml_result=result,
                        supplementary_message=values.get("SuppMsgOut"),
                        object_type=object_type,
                        selection=selection or {},
                    )
                )
                return _Invocation(
                    operation,
                    values,
                    response.body,
                    response.status,
                    request_id,
                    attempt,
                    self._monotonic() - started_all,
                )
            except (Witsml1411TransportError, Witsml1411SoapFault) as exc:
                last_error = exc
                duration = self._monotonic() - started
                status = response.status if response is not None else getattr(exc, "status", None)
                retryable = isinstance(exc, Witsml1411TransportError) and exc.retryable
                self.audit.record(
                    Witsml1411AuditEvent(
                        timestamp_utc=datetime.now(timezone.utc),
                        request_id=request_id,
                        operation=operation,
                        endpoint=sanitize_endpoint(self.profile.endpoint),
                        attempt=attempt,
                        outcome="retry" if retryable and attempt < self.profile.retry.max_attempts else "error",
                        duration_seconds=duration,
                        http_status=status,
                        supplementary_message=str(exc),
                        object_type=object_type,
                        selection=selection or {},
                    )
                )
                if not retryable or attempt >= self.profile.retry.max_attempts:
                    raise
                delay = min(
                    self.profile.retry.backoff_seconds * (2 ** (attempt - 1)),
                    self.profile.retry.max_backoff_seconds,
                )
                if delay:
                    self._sleep(delay)
        assert last_error is not None
        raise last_error


def _build_soap_envelope(operation: str, arguments: Mapping[str, str]) -> bytes:
    envelope = ET.Element(ET.QName(SOAP_ENV, "Envelope"))
    body = ET.SubElement(envelope, ET.QName(SOAP_ENV, "Body"))
    body.set(ET.QName(SOAP_ENV, "encodingStyle"), SOAP_ENC)
    operation_element = ET.SubElement(body, ET.QName(WITSML_MESSAGE, operation))
    for name, value in arguments.items():
        item = ET.SubElement(operation_element, name)
        item.set(ET.QName(XSI, "type"), "xsd:string")
        item.text = value
    return ET.tostring(envelope, encoding="utf-8", xml_declaration=True)


def _parse_soap_response(payload: bytes, operation: str) -> dict[str, str]:
    if not payload:
        raise Witsml1411Error("SOAP response is empty")
    lowered = payload[:8192].lower()
    if any(marker in lowered for marker in _FORBIDDEN_XML):
        raise Witsml1411Error("SOAP response contains a forbidden DTD/entity declaration")
    try:
        root = ET.fromstring(payload)
    except ET.ParseError as exc:
        raise Witsml1411Error(f"Invalid SOAP XML: {exc}") from exc
    body = next((item for item in root.iter() if _local(item.tag) == "Body"), None)
    if body is None:
        raise Witsml1411Error("SOAP Body is missing")
    fault = next((item for item in body if _local(item.tag) == "Fault"), None)
    if fault is not None:
        values = {_local(item.tag): (item.text or "").strip() for item in fault.iter()}
        raise Witsml1411SoapFault(values.get("faultcode"), values.get("faultstring"))
    expected = operation + "Response"
    response = next((item for item in body.iter() if _local(item.tag) == expected), None)
    if response is None:
        raise Witsml1411Error(f"SOAP response element is missing: {expected}")
    values: dict[str, str] = {}
    for item in response.iter():
        local = _local(item.tag)
        if local in {expected, "result"}:
            continue
        if item.text is not None:
            values[local] = item.text
    return values


def _parse_result(values: Mapping[str, str], operation: str) -> int:
    value = values.get("Result")
    try:
        return int(str(value).strip())
    except (TypeError, ValueError) as exc:
        raise Witsml1411Error(f"{operation} returned an invalid Result value: {value!r}") from exc


def _optional_int(value: str | None) -> int | None:
    if value is None:
        return None
    try:
        return int(value.strip())
    except ValueError:
        return None


def _local(tag: str) -> str:
    return tag.rsplit("}", 1)[-1]
