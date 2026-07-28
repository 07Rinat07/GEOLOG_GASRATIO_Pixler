from __future__ import annotations

import base64
from datetime import datetime, timezone
import importlib
import ssl
from typing import Any, Mapping
from uuid import uuid4

from geoworkbench import __version__
from geoworkbench.importers.etp12.models import (
    Etp12AuthMode,
    Etp12ConnectionProfile,
    Etp12Credentials,
    Etp12MessageHeader,
    Etp12ReceivedMessage,
)


class Etp12DependencyError(RuntimeError):
    pass


def _load(module: str, name: str):
    try:
        return getattr(importlib.import_module(module), name)
    except (ImportError, AttributeError) as exc:
        raise Etp12DependencyError(
            "ETP 1.2 runtime requires etpproto>=1.0.7, etptypes>=1.2.0, "
            "fastavro>=1.9 and websockets>=16"
        ) from exc


class EtpProtoMessageFactory:
    """Factory for generated Energistics ETP v1.2 Pydantic models."""

    def request_session(self, profile: Etp12ConnectionProfile) -> object:
        RequestSession = _load(
            "etptypes.energistics.etp.v12.protocol.core.request_session", "RequestSession"
        )
        SupportedProtocol = _load(
            "etptypes.energistics.etp.v12.datatypes.supported_protocol", "SupportedProtocol"
        )
        SupportedDataObject = _load(
            "etptypes.energistics.etp.v12.datatypes.supported_data_object", "SupportedDataObject"
        )
        Version = _load("etptypes.energistics.etp.v12.datatypes.version", "Version")
        DataValue = _load("etptypes.energistics.etp.v12.datatypes.data_value", "DataValue")
        version = Version(major=1, minor=2, revision=0, patch=0)
        requested = [
            SupportedProtocol(
                protocol=0,
                protocol_version=version,
                role="server",
                protocol_capabilities={},
            ),
            SupportedProtocol(
                protocol=1,
                protocol_version=version,
                role="producer",
                protocol_capabilities={},
            ),
            SupportedProtocol(
                protocol=3,
                protocol_version=version,
                role="store",
                protocol_capabilities={},
            ),
            SupportedProtocol(
                protocol=4,
                protocol_version=version,
                role="store",
                protocol_capabilities={},
            ),
            SupportedProtocol(
                protocol=9,
                protocol_version=version,
                role="store",
                protocol_capabilities={},
            ),
            SupportedProtocol(
                protocol=21,
                protocol_version=version,
                role="store",
                protocol_capabilities={},
            ),
        ]
        data_objects = [
            SupportedDataObject(qualified_type=value, data_object_capabilities={})
            for value in ("eml20.*", "eml23.*", "witsml20.*", "witsml21.*")
        ]
        now_us = int(datetime.now(timezone.utc).timestamp() * 1_000_000)
        return RequestSession(
            application_name="GEOLOG GASRATIO@Pixler",
            application_version=__version__,
            client_instance_id=uuid4(),
            requested_protocols=requested,
            supported_data_objects=data_objects,
            supported_compression=[],
            supported_formats=["xml"],
            current_date_time=now_us,
            earliest_retained_change_time=0,
            endpoint_capabilities={
                "MaxWebSocketMessagePayloadSize": DataValue(item=profile.max_message_bytes),
            },
        )

    def acknowledge(self) -> object:
        cls = _load("etptypes.energistics.etp.v12.protocol.core.acknowledge", "Acknowledge")
        return cls()

    def close_session(self, reason: str) -> object:
        cls = _load("etptypes.energistics.etp.v12.protocol.core.close_session", "CloseSession")
        return cls(reason=reason)

    def is_open_session(self, body: object) -> bool:
        return body.__class__.__name__ == "OpenSession"

    def is_acknowledge(self, body: object) -> bool:
        return body.__class__.__name__ == "Acknowledge"

    def is_protocol_exception(self, body: object) -> bool:
        return body.__class__.__name__ == "ProtocolException"

    def protocol_exception_message(self, body: object) -> str:
        error = getattr(body, "error", None)
        errors = getattr(body, "errors", None)
        parts: list[str] = []
        if error is not None:
            parts.append(_error_text(error))
        if isinstance(errors, Mapping):
            parts.extend(_error_text(value) for value in errors.values())
        return "; ".join(parts) or "Remote ETP ProtocolException"

    def get_resources(
        self,
        *,
        uri: str,
        depth: int = 1,
        data_object_types: tuple[str, ...] = (),
        scope: str = "targetsOrSelf",
        include_edges: bool = False,
        count_objects: bool = True,
    ) -> object:
        ContextInfo = _load(
            "etptypes.energistics.etp.v12.datatypes.object.context_info", "ContextInfo"
        )
        GetResources = _load(
            "etptypes.energistics.etp.v12.protocol.discovery.get_resources", "GetResources"
        )
        return GetResources(
            context=ContextInfo(
                uri=uri,
                depth=depth,
                data_object_types=list(data_object_types),
                navigable_edges="Primary",
                include_secondary_targets=False,
                include_secondary_sources=False,
            ),
            scope=scope,
            count_objects=count_objects,
            store_last_write_filter=None,
            active_status_filter=None,
            include_edges=include_edges,
        )

    def get_data_objects(self, uris: Mapping[str, str], *, format: str = "xml") -> object:
        cls = _load(
            "etptypes.energistics.etp.v12.protocol.store.get_data_objects", "GetDataObjects"
        )
        return cls(uris=dict(uris), format=format)

    def data_array_identifier(self, uri: str, path_in_resource: str) -> object:
        cls = _load(
            "etptypes.energistics.etp.v12.datatypes.data_array_types.data_array_identifier",
            "DataArrayIdentifier",
        )
        return cls(uri=uri, path_in_resource=path_in_resource)

    def get_data_array_metadata(self, arrays: Mapping[str, object]) -> object:
        cls = _load(
            "etptypes.energistics.etp.v12.protocol.data_array.get_data_array_metadata",
            "GetDataArrayMetadata",
        )
        return cls(data_arrays=dict(arrays))

    def get_data_arrays(self, arrays: Mapping[str, object]) -> object:
        cls = _load(
            "etptypes.energistics.etp.v12.protocol.data_array.get_data_arrays",
            "GetDataArrays",
        )
        return cls(data_arrays=dict(arrays))

    def get_channel_metadata(self, uris: Mapping[str, str]) -> object:
        cls = _load(
            "etptypes.energistics.etp.v12.protocol.channel_subscribe.get_channel_metadata",
            "GetChannelMetadata",
        )
        return cls(uris=dict(uris))

    def channel_subscribe_info(
        self,
        *,
        channel_id: int,
        start_index: object | None,
        data_changes: bool,
        request_latest_index_count: int | None,
    ) -> object:
        cls = _load(
            "etptypes.energistics.etp.v12.datatypes.channel_data.channel_subscribe_info",
            "ChannelSubscribeInfo",
        )
        IndexValue = _load("etptypes.energistics.etp.v12.datatypes.index_value", "IndexValue")
        index_value = _index_value(IndexValue, start_index)
        return cls(
            channel_id=channel_id,
            start_index=index_value,
            data_changes=data_changes,
            request_latest_index_count=request_latest_index_count,
        )

    def subscribe_channels(self, channels: Mapping[str, object]) -> object:
        cls = _load(
            "etptypes.energistics.etp.v12.protocol.channel_subscribe.subscribe_channels",
            "SubscribeChannels",
        )
        return cls(channels=dict(channels))

    def unsubscribe_channels(self, channel_ids: Mapping[str, int]) -> object:
        cls = _load(
            "etptypes.energistics.etp.v12.protocol.channel_subscribe.unsubscribe_channels",
            "UnsubscribeChannels",
        )
        return cls(channel_ids=dict(channel_ids))


class EtpProtoWebSocketAdapter:
    """Binary WebSocket adapter using generated etptypes and etpproto codecs."""

    SUBPROTOCOL = "etp12.energistics.org"

    def __init__(self) -> None:
        self.websocket: Any | None = None
        self._protocol_map: Any | None = None
        self._message_class: Any | None = None

    async def connect(
        self,
        profile: Etp12ConnectionProfile,
        credentials: Etp12Credentials,
    ) -> None:
        try:
            connect = _load("websockets.asyncio.client", "connect")
        except Etp12DependencyError:
            connect = _load("websockets", "connect")
        Message = _load("etpproto.messages", "Message")
        get_map = _load("etpproto.utils", "get_all_etp_protocol_classes")
        self._message_class = Message
        self._protocol_map = get_map()
        ssl_context: ssl.SSLContext | None = None
        if profile.endpoint.startswith("wss://"):
            ssl_context = ssl.create_default_context(cafile=profile.ca_file)
            if not profile.verify_tls:
                ssl_context.check_hostname = False
                ssl_context.verify_mode = ssl.CERT_NONE
        headers: dict[str, str] = {}
        if profile.auth_mode == Etp12AuthMode.BASIC:
            token = base64.b64encode(
                f"{credentials.username or profile.username}:{credentials.secret}".encode("utf-8")
            ).decode("ascii")
            headers["Authorization"] = f"Basic {token}"
        elif profile.auth_mode == Etp12AuthMode.BEARER:
            if not credentials.secret.strip():
                raise ValueError("Bearer token is empty")
            headers["Authorization"] = f"Bearer {credentials.secret.strip()}"
        kwargs: dict[str, object] = {
            "subprotocols": [self.SUBPROTOCOL],
            "ssl": ssl_context,
            "open_timeout": profile.open_timeout_seconds,
            "close_timeout": profile.close_timeout_seconds,
            "ping_interval": profile.ping_interval_seconds,
            "ping_timeout": profile.ping_timeout_seconds,
            "max_size": profile.max_message_bytes,
        }
        if headers:
            kwargs["additional_headers"] = headers
        self.websocket = await connect(profile.endpoint, **kwargs)
        negotiated = getattr(self.websocket, "subprotocol", None)
        if negotiated != self.SUBPROTOCOL:
            await self.websocket.close(code=1002, reason="ETP subprotocol was not negotiated")
            self.websocket = None
            raise RuntimeError(
                f"Server negotiated unexpected WebSocket subprotocol: {negotiated!r}"
            )

    async def send(
        self,
        body: object,
        *,
        message_id: int,
        correlation_id: int,
        message_flags: int,
    ) -> None:
        if self.websocket is None or self._message_class is None:
            raise RuntimeError("ETP WebSocket is not connected")
        message = self._message_class.get_object_message(
            body,
            msg_id=message_id,
            correlation_id=correlation_id,
            message_flags=message_flags,
        )
        if message is None:
            raise TypeError(f"Cannot encode ETP body {type(body).__name__}")
        payload = message.encode_message()
        await self.websocket.send(payload)

    async def recv(self) -> Etp12ReceivedMessage:
        if self.websocket is None or self._message_class is None or self._protocol_map is None:
            raise RuntimeError("ETP WebSocket is not connected")
        raw = await self.websocket.recv(decode=False)
        if not isinstance(raw, (bytes, bytearray, memoryview)):
            raise RuntimeError("ETP WebSocket returned a non-binary message")
        message = self._message_class.decode_binary_message(bytes(raw), self._protocol_map)
        if message is None:
            raise RuntimeError("Unable to decode ETP message")
        header = message.header
        return Etp12ReceivedMessage(
            header=Etp12MessageHeader(
                protocol=int(header.protocol),
                message_type=int(header.message_type),
                correlation_id=int(header.correlation_id),
                message_id=int(header.message_id),
                message_flags=int(header.message_flags),
            ),
            body=message.body,
            body_name=message.body.__class__.__name__,
        )

    async def close(self, reason: str) -> None:
        websocket = self.websocket
        self.websocket = None
        if websocket is not None:
            await websocket.close(code=1000, reason=reason[:120])


def _error_text(value: object) -> str:
    code = getattr(value, "code", None)
    message = getattr(value, "message", None)
    if code is None:
        return str(message or value)
    return f"{message or 'ETP error'} (code={code})"


def _index_value(IndexValue, value: object | None):
    if value is None:
        return IndexValue(item=None)
    if isinstance(value, bool):
        return IndexValue(item=int(value))
    if isinstance(value, datetime):
        aware = value if value.tzinfo is not None else value.replace(tzinfo=timezone.utc)
        return IndexValue(item=int(aware.astimezone(timezone.utc).timestamp() * 1_000_000))
    if isinstance(value, int):
        return IndexValue(item=value)
    if isinstance(value, float):
        return IndexValue(item=value)
    if isinstance(value, str):
        token = value.strip()
        if not token:
            return IndexValue(item=None)
        try:
            return IndexValue(item=int(token))
        except ValueError:
            pass
        try:
            return IndexValue(item=float(token))
        except ValueError:
            pass
        try:
            parsed = datetime.fromisoformat(token.replace("Z", "+00:00"))
        except ValueError as exc:
            raise ValueError(
                "ETP channel start index must be an integer, a number, or ISO-8601 time"
            ) from exc
        aware = parsed if parsed.tzinfo is not None else parsed.replace(tzinfo=timezone.utc)
        return IndexValue(item=int(aware.astimezone(timezone.utc).timestamp() * 1_000_000))
    raise TypeError(f"Unsupported ETP channel start index: {type(value).__name__}")
