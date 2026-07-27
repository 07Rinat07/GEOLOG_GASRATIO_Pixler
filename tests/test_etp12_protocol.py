from __future__ import annotations

import asyncio
from dataclasses import dataclass
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
from geoworkbench.importers.etp12.protocol import Etp12ProtocolEngine
from geoworkbench.services.etp12_audit import JsonlEtp12AuditSink


class RequestSession: pass
class OpenSession: pass
class Acknowledge: pass
class CloseSession:
    def __init__(self, reason: str) -> None:
        self.reason = reason
class ProtocolException:
    def __init__(self, message: str) -> None:
        self.error = SimpleNamespace(code=1, message=message)
        self.errors = {}
class Query: pass
class Response:
    def __init__(self, value: str) -> None:
        self.value = value
class ChannelData: pass


class FakeFactory:
    def request_session(self, profile): return RequestSession()
    def acknowledge(self): return Acknowledge()
    def close_session(self, reason): return CloseSession(reason)
    def is_open_session(self, body): return isinstance(body, OpenSession)
    def is_acknowledge(self, body): return isinstance(body, Acknowledge)
    def is_protocol_exception(self, body): return isinstance(body, ProtocolException)
    def protocol_exception_message(self, body): return body.error.message


class FakeAdapter:
    def __init__(self) -> None:
        self.incoming: asyncio.Queue[Etp12ReceivedMessage | BaseException] = asyncio.Queue()
        self.sent: list[tuple[object, int, int, int]] = []
        self.closed = False

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
                )
            )
        elif isinstance(body, Query):
            await self.incoming.put(
                Etp12ReceivedMessage(
                    Etp12MessageHeader(3, 2, message_id, 3, Etp12MessageHeader.ACK_REQUESTED),
                    Response("first"),
                    "Response",
                )
            )
            await self.incoming.put(
                Etp12ReceivedMessage(
                    Etp12MessageHeader(3, 2, message_id, 5, Etp12MessageHeader.FIN),
                    Response("second"),
                    "Response",
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
        ("wss://user:pass@example.com/etp", False, True),
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
    assert Etp12ConnectionProfile.from_public_dict(value) == profile()


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
    await value.connect(secure_profile, Etp12Credentials("reader", "secret"))

    kwargs = captured["kwargs"]
    assert kwargs["subprotocols"] == ["etp12.energistics.org"]
    assert kwargs["max_size"] == 128 * 1024
    assert kwargs["additional_headers"]["Authorization"] == (
        "Basic " + base64.b64encode(b"reader:secret").decode("ascii")
    )
    await value.close("done")
