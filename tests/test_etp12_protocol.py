from __future__ import annotations

import asyncio
import json
from pathlib import Path
from types import SimpleNamespace

import pytest

from geoworkbench.importers.etp12.models import (
    Etp12ConnectionProfile,
    Etp12Credentials,
    Etp12MessageHeader,
    Etp12ReceivedMessage,
    Etp12SessionState,
)
from geoworkbench.importers.etp12.protocol import (
    Etp12MultipartLimitError,
    Etp12MultipartTimeout,
    Etp12ProtocolEngine,
    Etp12RequestTimeout,
)
from geoworkbench.services.etp12_audit import JsonlEtp12AuditSink


class RequestSession:
    pass


class OpenSession:
    pass


class Acknowledge:
    pass


class CloseSession:
    def __init__(self, reason: str) -> None:
        self.reason = reason


class ProtocolException:
    def __init__(self, message: str) -> None:
        self.error = SimpleNamespace(code=1, message=message)
        self.errors = {}


class Query:
    pass


class Response:
    def __init__(self, value: str) -> None:
        self.value = value


class ChannelData:
    pass


class FakeFactory:
    def request_session(self, profile): return RequestSession()
    def acknowledge(self): return Acknowledge()
    def close_session(self, reason): return CloseSession(reason)
    def is_open_session(self, body): return isinstance(body, OpenSession)
    def is_acknowledge(self, body): return isinstance(body, Acknowledge)
    def is_protocol_exception(self, body): return isinstance(body, ProtocolException)
    def protocol_exception_message(self, body): return body.error.message


class FakeAdapter:
    def __init__(
        self,
        *,
        query_sizes: tuple[int, int] = (96, 96),
        finish_query: bool = True,
    ) -> None:
        self.incoming: asyncio.Queue[Etp12ReceivedMessage | BaseException] = asyncio.Queue()
        self.sent: list[tuple[object, int, int, int]] = []
        self.closed = False
        self.query_sizes = query_sizes
        self.finish_query = finish_query

    async def connect(self, profile, credentials) -> None:
        self.profile = profile
        self.credentials = credentials

    async def send(self, body, *, message_id, correlation_id, message_flags) -> None:
        self.sent.append((body, message_id, correlation_id, message_flags))
        if isinstance(body, RequestSession):
            await self.incoming.put(
                Etp12ReceivedMessage(
                    Etp12MessageHeader(0, 2, message_id, 1, Etp12MessageHeader.FIN),
                    OpenSession(),
                    "OpenSession",
                    64,
                )
            )
        elif isinstance(body, Query):
            await self.incoming.put(
                Etp12ReceivedMessage(
                    Etp12MessageHeader(3, 2, message_id, 3, Etp12MessageHeader.ACK_REQUESTED),
                    Response("first"),
                    "Response",
                    self.query_sizes[0],
                )
            )
            if self.finish_query:
                await self.incoming.put(
                    Etp12ReceivedMessage(
                        Etp12MessageHeader(3, 2, message_id, 5, Etp12MessageHeader.FIN),
                        Response("second"),
                        "Response",
                        self.query_sizes[1],
                    )
                )

    async def recv(self):
        value = await self.incoming.get()
        if isinstance(value, BaseException):
            raise value
        return value

    async def close(self, reason: str) -> None:
        self.closed = True


def profile() -> Etp12ConnectionProfile:
    return Etp12ConnectionProfile(
        profile_id="local",
        name="Local",
        endpoint="ws://localhost:9002/etp",
        allow_insecure_localhost=True,
    )


@pytest.mark.asyncio
async def test_protocol_engine_correlates_multipart_and_sends_ack(tmp_path: Path) -> None:
    adapter = FakeAdapter()
    audit = JsonlEtp12AuditSink(tmp_path / "audit.jsonl", fsync=False)
    engine = Etp12ProtocolEngine(adapter, FakeFactory(), audit=audit.record)
    await engine.connect(profile(), Etp12Credentials())
    assert engine.state == Etp12SessionState.OPEN

    responses = await engine.request(Query())
    assert [item.body.value for item in responses] == ["first", "second"]
    assert engine.acknowledgements_sent == 1
    ack_rows = [row for row in adapter.sent if isinstance(row[0], Acknowledge)]
    assert len(ack_rows) == 1
    assert ack_rows[0][2] == 3  # acknowledge the server message id
    assert ack_rows[0][3] == Etp12MessageHeader.FIN
    assert audit.verify()[0] >= 5
    await engine.close()


@pytest.mark.asyncio
async def test_protocol_engine_rejects_too_many_multipart_parts(tmp_path: Path) -> None:
    adapter = FakeAdapter()
    audit_path = tmp_path / "limit-audit.jsonl"
    audit = JsonlEtp12AuditSink(audit_path, fsync=False)
    engine = Etp12ProtocolEngine(adapter, FakeFactory(), audit=audit.record)
    limited = Etp12ConnectionProfile(
        profile_id="parts",
        name="Parts",
        endpoint="ws://localhost:9002/etp",
        allow_insecure_localhost=True,
        max_multipart_parts=1,
    )
    await engine.connect(limited, Etp12Credentials())

    with pytest.raises(Etp12MultipartLimitError, match="exceeded the part limit of 1"):
        await engine.request(Query())

    assert engine.state is Etp12SessionState.FAILED
    assert adapter.closed is True
    assert engine.pending_count == 0
    rows = [json.loads(line) for line in audit_path.read_text(encoding="utf-8").splitlines()]
    failure = next(row for row in rows if row["event"] == "multipart")
    assert failure["metadata"] == {
        "encoded_size_bytes": 192,
        "limit": "parts",
        "parts": 2,
    }


@pytest.mark.asyncio
async def test_protocol_engine_rejects_multipart_encoded_byte_budget() -> None:
    adapter = FakeAdapter(query_sizes=(40 * 1024, 40 * 1024))
    engine = Etp12ProtocolEngine(adapter, FakeFactory())
    limited = Etp12ConnectionProfile(
        profile_id="bytes",
        name="Bytes",
        endpoint="ws://localhost:9002/etp",
        allow_insecure_localhost=True,
        max_multipart_bytes=64 * 1024,
    )
    await engine.connect(limited, Etp12Credentials())

    with pytest.raises(Etp12MultipartLimitError, match="exceeded the encoded-size limit of 65536 bytes"):
        await engine.request(Query())

    assert engine.state is Etp12SessionState.FAILED
    assert adapter.closed is True


@pytest.mark.asyncio
async def test_protocol_engine_expires_incomplete_multipart_assembly() -> None:
    adapter = FakeAdapter(finish_query=False)
    engine = Etp12ProtocolEngine(adapter, FakeFactory())
    limited = Etp12ConnectionProfile(
        profile_id="timeout",
        name="Timeout",
        endpoint="ws://localhost:9002/etp",
        allow_insecure_localhost=True,
        request_timeout_seconds=1.0,
        multipart_timeout_seconds=0.01,
    )
    await engine.connect(limited, Etp12Credentials())

    with pytest.raises(Etp12MultipartTimeout, match="did not finish within 0.01 seconds"):
        await engine.request(Query())

    assert engine.state is Etp12SessionState.FAILED
    assert adapter.closed is True
    assert engine.pending_count == 0


@pytest.mark.asyncio
async def test_request_timeout_closes_started_multipart_session() -> None:
    adapter = FakeAdapter(finish_query=False)
    engine = Etp12ProtocolEngine(adapter, FakeFactory())
    limited = Etp12ConnectionProfile(
        profile_id="request-timeout",
        name="Request timeout",
        endpoint="ws://localhost:9002/etp",
        allow_insecure_localhost=True,
        request_timeout_seconds=1.0,
        multipart_timeout_seconds=1.0,
    )
    await engine.connect(limited, Etp12Credentials())

    with pytest.raises(Etp12RequestTimeout, match="timed out after 0.01 seconds"):
        await engine.request(Query(), timeout=0.01)

    assert engine.state is Etp12SessionState.FAILED
    assert adapter.closed is True
    assert engine.pending_count == 0


@pytest.mark.asyncio
async def test_protocol_engine_dispatches_unsolicited_channel_data() -> None:
    adapter = FakeAdapter()
    engine = Etp12ProtocolEngine(adapter, FakeFactory())
    received: list[Etp12ReceivedMessage] = []

    async def handler(message):
        received.append(message)

    engine.add_unsolicited_handler(handler)
    await engine.connect(profile(), Etp12Credentials())
    await adapter.incoming.put(
        Etp12ReceivedMessage(
            Etp12MessageHeader(21, 4, 0, 7, Etp12MessageHeader.FIN),
            ChannelData(),
            "ChannelData",
            80,
        )
    )
    await asyncio.sleep(0)
    assert len(received) == 1
    assert received[0].header.protocol == 21
    await engine.close()


@pytest.mark.parametrize(
    "endpoint,allow,verify",
    [
        ("ws://example.com/etp", False, True),
        ("wss://user:pass@example.com/etp", False, True),  # pragma: allowlist secret
        ("wss://example.com/etp", False, False),
    ],
)
def test_profile_rejects_insecure_or_embedded_credentials(endpoint, allow, verify) -> None:
    with pytest.raises(ValueError):
        Etp12ConnectionProfile(
            profile_id="bad",
            name="Bad",
            endpoint=endpoint,
            allow_insecure_localhost=allow,
            verify_tls=verify,
        )


def test_profile_public_serialization_has_no_secret() -> None:
    value = profile().to_public_dict()
    text = repr(value).casefold()
    assert "password" not in text
    assert "bearer" not in text
    assert value["max_multipart_bytes"] == 64 * 1024 * 1024
    assert value["max_multipart_parts"] == 256
    assert value["multipart_timeout_seconds"] == 30.0
    assert Etp12ConnectionProfile.from_public_dict(value) == profile()


@pytest.mark.parametrize(
    ("field_name", "value", "message"),
    [
        ("max_multipart_bytes", True, "max_multipart_bytes must be an integer"),
        ("max_multipart_parts", False, "max_multipart_parts must be an integer"),
        (
            "multipart_timeout_seconds",
            True,
            "multipart_timeout_seconds must be numeric",
        ),
    ],
)
def test_profile_public_serialization_rejects_invalid_multipart_limits(
    field_name: str,
    value: object,
    message: str,
) -> None:
    payload = profile().to_public_dict()
    payload[field_name] = value

    with pytest.raises(TypeError, match=message):
        Etp12ConnectionProfile.from_public_dict(payload)


def test_received_message_requires_positive_encoded_size() -> None:
    header = Etp12MessageHeader(3, 2, 2, 1, Etp12MessageHeader.FIN)

    with pytest.raises(ValueError, match="positive integer"):
        Etp12ReceivedMessage(header, Response("bad"), "Response", 0)
    with pytest.raises(ValueError, match="positive integer"):
        Etp12ReceivedMessage(header, Response("bad"), "Response", 1.5)  # type: ignore[arg-type]


def test_profile_public_serialization_rejects_non_numeric_limits() -> None:
    value = profile().to_public_dict()
    value["request_timeout_seconds"] = object()

    with pytest.raises(TypeError, match="request_timeout_seconds must be numeric"):
        Etp12ConnectionProfile.from_public_dict(value)


def test_profile_public_serialization_rejects_boolean_timeout_from_json() -> None:
    value = json.loads(json.dumps(profile().to_public_dict()))
    value["request_timeout_seconds"] = True

    with pytest.raises(TypeError, match="request_timeout_seconds must be numeric"):
        Etp12ConnectionProfile.from_public_dict(value)


@pytest.mark.parametrize(
    ("field_name", "value", "message"),
    [
        ("max_attempts", False, "max_attempts must be an integer"),
        ("multiplier", True, "multiplier must be numeric"),
    ],
)
def test_profile_public_serialization_rejects_boolean_reconnect_fields_from_json(
    field_name: str,
    value: bool,
    message: str,
) -> None:
    payload = json.loads(json.dumps(profile().to_public_dict()))
    reconnect = payload["reconnect"]
    assert isinstance(reconnect, dict)
    reconnect[field_name] = value

    with pytest.raises(TypeError, match=message):
        Etp12ConnectionProfile.from_public_dict(payload)


@pytest.mark.asyncio
async def test_websocket_adapter_uses_etp_subprotocol_and_basic_auth(monkeypatch) -> None:
    import base64

    import geoworkbench.importers.etp12.etpproto_adapter as adapter_module
    from geoworkbench.importers.etp12.etpproto_adapter import EtpProtoWebSocketAdapter
    from geoworkbench.importers.etp12.models import Etp12AuthMode

    captured = {}

    class FakeWebSocket:
        subprotocol = "etp12.energistics.org"

        async def close(self, **kwargs):
            captured["closed"] = kwargs

    async def fake_connect(endpoint, **kwargs):
        captured["endpoint"] = endpoint
        captured["kwargs"] = kwargs
        return FakeWebSocket()

    def fake_load(module, name):
        if name == "connect":
            return fake_connect
        if name == "Message":
            return object
        if name == "get_all_etp_protocol_classes":
            return lambda: {}
        raise AssertionError((module, name))

    monkeypatch.setattr(adapter_module, "_load", fake_load)
    value = EtpProtoWebSocketAdapter()
    secure_profile = Etp12ConnectionProfile(
        profile_id="basic",
        name="Basic",
        endpoint="ws://localhost:9002/etp",
        auth_mode=Etp12AuthMode.BASIC,
        username="reader",
        allow_insecure_localhost=True,
        max_message_bytes=128 * 1024,
    )
    # pragma: allowlist nextline secret
    await value.connect(
        secure_profile, Etp12Credentials("reader", "secret")
    )

    kwargs = captured["kwargs"]
    assert kwargs["subprotocols"] == ["etp12.energistics.org"]
    assert kwargs["max_size"] == 128 * 1024
    assert kwargs["additional_headers"]["Authorization"] == (
        "Basic " + base64.b64encode(b"reader:secret").decode("ascii")  # pragma: allowlist secret
    )
    await value.close("done")


@pytest.mark.asyncio
async def test_websocket_adapter_reports_binary_frame_size() -> None:
    from geoworkbench.importers.etp12.etpproto_adapter import EtpProtoWebSocketAdapter

    payload = b"\x01\x02\x03\x04\x05"

    class FakeWebSocket:
        async def recv(self, *, decode=False):
            assert decode is False
            return payload

    class FakeMessageClass:
        @staticmethod
        def decode_binary_message(raw, protocol_map):
            assert raw == payload
            assert protocol_map == {"ready": True}
            return SimpleNamespace(
                header=SimpleNamespace(
                    protocol=3,
                    message_type=2,
                    correlation_id=2,
                    message_id=3,
                    message_flags=Etp12MessageHeader.FIN,
                ),
                body=Response("ok"),
            )

    adapter = EtpProtoWebSocketAdapter()
    adapter.websocket = FakeWebSocket()
    adapter._message_class = FakeMessageClass
    adapter._protocol_map = {"ready": True}

    received = await adapter.recv()

    assert received.encoded_size_bytes == len(payload)
    assert received.body_name == "Response"
