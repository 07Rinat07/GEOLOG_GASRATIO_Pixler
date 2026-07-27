from __future__ import annotations

import asyncio
from dataclasses import replace
from datetime import datetime, timezone
from typing import Awaitable, Callable, Iterable, Mapping, Sequence

from geoworkbench.importers.etp12.etpproto_adapter import (
    EtpProtoMessageFactory,
    EtpProtoWebSocketAdapter,
)
from geoworkbench.importers.etp12.models import (
    Etp12ChannelBatch,
    Etp12ChannelMetadata,
    Etp12ChannelPoint,
    Etp12ConnectionProfile,
    Etp12Credentials,
    Etp12DataArray,
    Etp12DataArrayIdentifier,
    Etp12DataArrayMetadata,
    Etp12DataObject,
    Etp12NegotiatedSession,
    Etp12Protocol,
    Etp12ReceivedMessage,
    Etp12Resource,
    Etp12Role,
    Etp12SessionSnapshot,
    Etp12SessionState,
    Etp12SubscriptionDefinition,
    Etp12SubscriptionSnapshot,
    Etp12SubscriptionState,
    Etp12SupportedProtocol,
)
from geoworkbench.importers.etp12.protocol import (
    AuditCallback,
    Etp12ProtocolEngine,
)


ChannelCallback = Callable[[Etp12ChannelBatch], Awaitable[None] | None]
EngineFactory = Callable[[], tuple[Etp12ProtocolEngine, EtpProtoMessageFactory]]


class Etp12UnsupportedProtocolError(RuntimeError):
    pass


class Etp12ClientService:
    """Read-only ETP v1.2 facade with reconnectable channel subscriptions."""

    def __init__(
        self,
        profile: Etp12ConnectionProfile,
        credentials: Etp12Credentials = Etp12Credentials(),
        *,
        audit: AuditCallback | None = None,
        engine_factory: EngineFactory | None = None,
    ) -> None:
        self.profile = profile
        self.credentials = credentials
        self.audit = audit
        self._engine_factory = engine_factory or self._default_engine_factory
        self.engine: Etp12ProtocolEngine | None = None
        self.factory: EtpProtoMessageFactory | None = None
        self.negotiated: Etp12NegotiatedSession | None = None
        self.generation = 0
        self.reconnect_attempt = 0
        self.last_error: str | None = None
        self._subscriptions: dict[str, Etp12SubscriptionSnapshot] = {}
        self._channel_callbacks: list[ChannelCallback] = []
        self._connect_lock = asyncio.Lock()
        self._watchdog_task: asyncio.Task[None] | None = None
        self._closing = False
        self._reconnecting = False
        self._watchdog_interval_seconds = 0.5

    def _default_engine_factory(self) -> tuple[Etp12ProtocolEngine, EtpProtoMessageFactory]:
        factory = EtpProtoMessageFactory()
        adapter = EtpProtoWebSocketAdapter()
        engine = Etp12ProtocolEngine(adapter, factory, audit=self.audit)
        return engine, factory

    @property
    def state(self) -> Etp12SessionState:
        if self._reconnecting:
            return Etp12SessionState.RECONNECTING
        return self.engine.state if self.engine is not None else Etp12SessionState.DISCONNECTED

    def add_channel_callback(self, callback: ChannelCallback) -> None:
        if callback not in self._channel_callbacks:
            self._channel_callbacks.append(callback)

    def remove_channel_callback(self, callback: ChannelCallback) -> None:
        if callback in self._channel_callbacks:
            self._channel_callbacks.remove(callback)

    async def connect(self) -> Etp12NegotiatedSession:
        self._closing = False
        async with self._connect_lock:
            if self.engine is not None and self.engine.state == Etp12SessionState.OPEN:
                assert self.negotiated is not None
                return self.negotiated
            engine, factory = self._engine_factory()
            engine.add_unsolicited_handler(self._handle_unsolicited)
            messages = await engine.connect(self.profile, self.credentials)
            negotiated = _parse_open_session(messages[0].body)
            self._validate_negotiated(negotiated)
            self.engine = engine
            self.factory = factory
            self.negotiated = negotiated
            self.generation += 1
            self.reconnect_attempt = 0
            self.last_error = None
            await self.restore_subscriptions()
            self._ensure_watchdog_started()
            return negotiated

    async def reconnect(self) -> Etp12NegotiatedSession:
        self._closing = False
        self._reconnecting = True
        try:
            return await self._reconnect_locked()
        finally:
            self._reconnecting = False

    async def _reconnect_locked(self) -> Etp12NegotiatedSession:
        async with self._connect_lock:
            if self.engine is not None:
                try:
                    await self.engine.close("Reconnecting")
                except Exception:
                    pass
            last_error: BaseException | None = None
            policy = self.profile.reconnect
            for attempt in range(1, policy.max_attempts + 1):
                self.reconnect_attempt = attempt
                for key, snapshot in tuple(self._subscriptions.items()):
                    self._subscriptions[key] = replace(
                        snapshot,
                        state=Etp12SubscriptionState.RESTORING,
                        last_error=None,
                    )
                if attempt > 1:
                    await asyncio.sleep(policy.delay_for_attempt(attempt - 1))
                engine, factory = self._engine_factory()
                engine.add_unsolicited_handler(self._handle_unsolicited)
                try:
                    messages = await engine.connect(self.profile, self.credentials)
                    negotiated = _parse_open_session(messages[0].body)
                    self._validate_negotiated(negotiated)
                    self.engine = engine
                    self.factory = factory
                    self.negotiated = negotiated
                    self.generation += 1
                    self.reconnect_attempt = 0
                    self.last_error = None
                    await self.restore_subscriptions()
                    self._ensure_watchdog_started()
                    return negotiated
                except Exception as exc:
                    last_error = exc
                    self.last_error = str(exc)
                    try:
                        await engine.close("Reconnect attempt failed")
                    except Exception:
                        pass
            assert last_error is not None
            for key, snapshot in tuple(self._subscriptions.items()):
                self._subscriptions[key] = replace(
                    snapshot,
                    state=Etp12SubscriptionState.SUSPENDED,
                    last_error=str(last_error),
                )
            raise last_error

    async def ensure_connected(self) -> Etp12NegotiatedSession:
        if self.engine is not None and self.engine.state == Etp12SessionState.OPEN:
            assert self.negotiated is not None
            return self.negotiated
        if self.engine is None or self.engine.state in {
            Etp12SessionState.DISCONNECTED,
            Etp12SessionState.CLOSED,
        }:
            return await self.connect()
        return await self.reconnect()

    async def close(self) -> None:
        self._closing = True
        await self._cancel_watchdog()
        if self.engine is not None:
            await self.engine.close("Client closed by operator")
        for key, snapshot in tuple(self._subscriptions.items()):
            self._subscriptions[key] = replace(snapshot, state=Etp12SubscriptionState.CLOSED)

    def _ensure_watchdog_started(self) -> None:
        if self._closing:
            return
        task = self._watchdog_task
        if task is None or task.done():
            self._watchdog_task = asyncio.create_task(
                self._watchdog_loop(),
                name=f"etp12-watchdog-{self.profile.profile_id}",
            )

    async def _cancel_watchdog(self) -> None:
        task = self._watchdog_task
        self._watchdog_task = None
        if task is None or task.done() or task is asyncio.current_task():
            return
        task.cancel()
        try:
            await task
        except asyncio.CancelledError:
            pass

    async def _watchdog_loop(self) -> None:
        """Reconnect a failed WebSocket session and restore subscriptions.

        The protocol engine changes to FAILED when its receive loop exits.  The
        watchdog owns no socket and performs no protocol work itself; it only
        invokes the same bounded reconnect path used by an explicit operator
        action.  If a complete retry cycle fails, it waits before starting a new
        cycle so a long outage cannot create a tight reconnect loop.
        """

        try:
            while not self._closing:
                await asyncio.sleep(self._watchdog_interval_seconds)
                engine = self.engine
                if engine is None or engine.state != Etp12SessionState.FAILED:
                    continue
                self.last_error = engine.last_error or self.last_error
                try:
                    await self.reconnect()
                except asyncio.CancelledError:
                    raise
                except Exception as exc:
                    self.last_error = str(exc)
                    if self._closing:
                        return
                    await asyncio.sleep(
                        max(
                            self._watchdog_interval_seconds,
                            self.profile.reconnect.max_backoff_seconds,
                        )
                    )
        except asyncio.CancelledError:
            raise

    async def discover(
        self,
        uri: str,
        *,
        depth: int = 1,
        data_object_types: Iterable[str] = (),
        scope: str = "targetsOrSelf",
        include_edges: bool = False,
    ) -> tuple[Etp12Resource, ...]:
        engine, factory = await self._ready(Etp12Protocol.DISCOVERY)
        responses = await engine.request(
            factory.get_resources(
                uri=uri,
                depth=depth,
                data_object_types=tuple(data_object_types),
                scope=scope,
                include_edges=include_edges,
            )
        )
        resources: list[Etp12Resource] = []
        for response in responses:
            values = getattr(response.body, "resources", ())
            for value in values:
                resources.append(_parse_resource(value))
        return tuple(resources)

    async def get_data_objects(
        self,
        uris: Mapping[str, str],
        *,
        format: str = "xml",
    ) -> Mapping[str, Etp12DataObject]:
        engine, factory = await self._ready(Etp12Protocol.STORE)
        responses = await engine.request(factory.get_data_objects(uris, format=format))
        result: dict[str, Etp12DataObject] = {}
        for response in responses:
            values = getattr(response.body, "data_objects", {})
            for key, value in _mapping_items(values):
                resource = getattr(value, "resource", None)
                data = getattr(value, "data", b"")
                if isinstance(data, str):
                    raw = data.encode("utf-8")
                else:
                    raw = bytes(data or b"")
                result[str(key)] = Etp12DataObject(
                    uri=(getattr(resource, "uri", None) or str(key)),
                    resource=_parse_resource(resource) if resource is not None else None,
                    format=str(getattr(value, "format", format)),
                    data=raw,
                    blob_id=(str(getattr(value, "blob_id")) if getattr(value, "blob_id", None) else None),
                )
        return result

    async def get_data_array_metadata(
        self,
        identifiers: Sequence[Etp12DataArrayIdentifier],
    ) -> Mapping[str, Etp12DataArrayMetadata]:
        engine, factory = await self._ready(Etp12Protocol.DATA_ARRAY)
        wire = {
            item.key: factory.data_array_identifier(item.uri, item.path_in_resource)
            for item in identifiers
        }
        responses = await engine.request(factory.get_data_array_metadata(wire))
        by_key = {item.key: item for item in identifiers}
        result: dict[str, Etp12DataArrayMetadata] = {}
        for response in responses:
            values = getattr(response.body, "array_metadata", {})
            for key, value in _mapping_items(values):
                token = str(key)
                identifier = by_key.get(token) or _parse_array_identifier(token, value)
                result[token] = Etp12DataArrayMetadata(
                    key=token,
                    identifier=identifier,
                    dimensions=tuple(int(v) for v in getattr(value, "dimensions", ()) or ()),
                    transport_array_type=_string_or_none(getattr(value, "transport_array_type", None)),
                    logical_array_type=_string_or_none(getattr(value, "logical_array_type", None)),
                    store_last_write=_int_or_none(getattr(value, "store_last_write", None)),
                )
        return result

    async def get_data_arrays(
        self,
        identifiers: Sequence[Etp12DataArrayIdentifier],
    ) -> Mapping[str, Etp12DataArray]:
        engine, factory = await self._ready(Etp12Protocol.DATA_ARRAY)
        wire = {
            item.key: factory.data_array_identifier(item.uri, item.path_in_resource)
            for item in identifiers
        }
        responses = await engine.request(factory.get_data_arrays(wire))
        by_key = {item.key: item for item in identifiers}
        result: dict[str, Etp12DataArray] = {}
        for response in responses:
            values = getattr(response.body, "data_arrays", {})
            for key, value in _mapping_items(values):
                token = str(key)
                identifier = by_key.get(token) or _parse_array_identifier(token, value)
                dimensions = tuple(int(v) for v in getattr(value, "dimensions", ()) or ())
                array_value = getattr(value, "data", value)
                result[token] = Etp12DataArray(token, identifier, dimensions, _unwrap(array_value))
        return result

    async def get_channel_metadata(
        self,
        uris: Mapping[str, str],
    ) -> Mapping[str, Etp12ChannelMetadata]:
        engine, factory = await self._ready(Etp12Protocol.CHANNEL_SUBSCRIBE)
        responses = await engine.request(factory.get_channel_metadata(uris))
        result: dict[str, Etp12ChannelMetadata] = {}
        for response in responses:
            metadata = getattr(response.body, "metadata", {})
            for key, value in _mapping_items(metadata):
                token = str(key)
                indexes = tuple(getattr(value, "indexes", ()) or ())
                first_index = indexes[0] if indexes else None
                result[token] = Etp12ChannelMetadata(
                    channel_id=int(getattr(value, "id")),
                    channel_uri=str(getattr(value, "uri")),
                    channel_name=str(getattr(value, "channel_name", token)),
                    data_kind=_string_or_none(getattr(value, "data_kind", None)),
                    uom=_string_or_none(getattr(value, "uom", None)),
                    index_kind=_string_or_none(
                        getattr(first_index, "index_kind", None) if first_index is not None else None
                    ),
                    start_index=_unwrap(
                        getattr(first_index, "minimum_value", None) if first_index is not None else None
                    ),
                    end_index=_unwrap(
                        getattr(first_index, "maximum_value", None) if first_index is not None else None
                    ),
                    description=_string_or_none(getattr(value, "source", None)),
                    custom_data=_public_mapping(getattr(value, "custom_data", {})),
                )
        return result

    async def subscribe(self, definition: Etp12SubscriptionDefinition) -> Etp12SubscriptionSnapshot:
        metadata = await self.get_channel_metadata(
            {str(index): uri for index, uri in enumerate(definition.channel_uris)}
        )
        if len(metadata) != len(definition.channel_uris):
            missing = sorted(set(definition.channel_uris).difference(
                item.channel_uri for item in metadata.values()
            ))
            raise ValueError(f"Server did not return channel metadata for: {', '.join(missing)}")
        engine, factory = await self._ready(Etp12Protocol.CHANNEL_SUBSCRIBE)
        channels: dict[str, object] = {}
        channel_ids: dict[str, int] = {}
        for key, item in metadata.items():
            channel_ids[item.channel_uri] = item.channel_id
            channels[key] = factory.channel_subscribe_info(
                channel_id=item.channel_id,
                start_index=definition.start_index,
                data_changes=definition.data_changes,
                request_latest_index_count=(1 if definition.request_latest_values else None),
            )
        existing = self._subscriptions.get(definition.subscription_id)
        generation = (existing.generation + 1) if existing is not None else 1
        self._subscriptions[definition.subscription_id] = Etp12SubscriptionSnapshot(
            definition=definition,
            state=Etp12SubscriptionState.PENDING,
            generation=generation,
            channel_ids=channel_ids,
        )
        responses = await engine.request(factory.subscribe_channels(channels))
        success: dict[str, str] = {}
        for response in responses:
            success.update({str(k): str(v) for k, v in _mapping_items(getattr(response.body, "success", {}))})
        snapshot = Etp12SubscriptionSnapshot(
            definition=definition,
            state=Etp12SubscriptionState.ACTIVE,
            generation=generation,
            server_subscription_id=None,
            channel_ids=channel_ids,
            last_indexes=(existing.last_indexes if existing is not None else {}),
        )
        self._subscriptions[definition.subscription_id] = snapshot
        return snapshot

    async def unsubscribe(self, subscription_id: str) -> None:
        snapshot = self._subscriptions.get(subscription_id)
        if snapshot is None:
            return
        if snapshot.channel_ids and self.state == Etp12SessionState.OPEN:
            engine, factory = await self._ready(Etp12Protocol.CHANNEL_SUBSCRIBE)
            payload = {str(index): channel_id for index, channel_id in enumerate(snapshot.channel_ids.values())}
            await engine.request(factory.unsubscribe_channels(payload))
        self._subscriptions[subscription_id] = replace(
            snapshot, state=Etp12SubscriptionState.CLOSED
        )

    async def restore_subscriptions(self) -> tuple[Etp12SubscriptionSnapshot, ...]:
        definitions = [
            snapshot.definition
            for snapshot in self._subscriptions.values()
            if snapshot.state not in {Etp12SubscriptionState.CLOSED, Etp12SubscriptionState.FAILED}
        ]
        restored: list[Etp12SubscriptionSnapshot] = []
        for definition in definitions:
            previous = self._subscriptions[definition.subscription_id]
            start_index = definition.start_index
            if previous.last_indexes:
                # Resume from the greatest retained index. The server remains the
                # authority and may return overlap; downstream acquisition deduplicates.
                try:
                    start_index = max(previous.last_indexes.values())
                except TypeError:
                    start_index = next(reversed(tuple(previous.last_indexes.values())))
            try:
                restored.append(await self.subscribe(replace(definition, start_index=start_index)))
            except Exception as exc:
                self._subscriptions[definition.subscription_id] = replace(
                    previous,
                    state=Etp12SubscriptionState.SUSPENDED,
                    last_error=str(exc),
                )
        return tuple(restored)

    def snapshot(self) -> Etp12SessionSnapshot:
        engine = self.engine
        return Etp12SessionSnapshot(
            state=self.state,
            generation=self.generation,
            negotiated=self.negotiated,
            reconnect_attempt=self.reconnect_attempt,
            sent_messages=engine.sent_messages if engine is not None else 0,
            received_messages=engine.received_messages if engine is not None else 0,
            acknowledgements_sent=engine.acknowledgements_sent if engine is not None else 0,
            acknowledgements_received=engine.acknowledgements_received if engine is not None else 0,
            pending_requests=engine.pending_count if engine is not None else 0,
            subscriptions=tuple(self._subscriptions.values()),
            last_error=self.last_error or (engine.last_error if engine is not None else None),
        )

    async def _ready(
        self, protocol: Etp12Protocol
    ) -> tuple[Etp12ProtocolEngine, EtpProtoMessageFactory]:
        negotiated = await self.ensure_connected()
        if not negotiated.supports(protocol):
            raise Etp12UnsupportedProtocolError(
                f"Server did not negotiate ETP protocol {protocol.value} ({protocol.name})"
            )
        assert self.engine is not None and self.factory is not None
        return self.engine, self.factory

    def _validate_negotiated(self, negotiated: Etp12NegotiatedSession) -> None:
        required = {Etp12Protocol.CORE}
        missing = [item.name for item in required if not negotiated.supports(item)]
        if missing:
            raise ValueError(f"Server OpenSession omitted required protocols: {', '.join(missing)}")
        if "xml" not in {item.casefold() for item in negotiated.supported_formats}:
            raise ValueError("Server did not negotiate XML data-object format")

    async def _handle_unsolicited(self, message: Etp12ReceivedMessage) -> None:
        if message.body_name not in {
            "ChannelData",
            "ChannelsTruncated",
            "RangeReplaced",
            "SubscriptionsStopped",
        }:
            return
        if message.body_name == "SubscriptionsStopped":
            reason = _string_or_none(getattr(message.body, "reason", None)) or "Server stopped subscriptions"
            for key, snapshot in tuple(self._subscriptions.items()):
                self._subscriptions[key] = replace(
                    snapshot,
                    state=Etp12SubscriptionState.SUSPENDED,
                    last_error=reason,
                )
            return
        if message.body_name != "ChannelData":
            return
        points: list[Etp12ChannelPoint] = []
        for item in getattr(message.body, "data", ()) or ():
            indexes = tuple(_unwrap(value) for value in getattr(item, "indexes", ()) or ())
            index = indexes[0] if indexes else None
            channel_id = int(getattr(item, "channel_id"))
            points.append(
                Etp12ChannelPoint(
                    channel_id=channel_id,
                    index=index,
                    value=_unwrap(getattr(item, "value", None)),
                    value_attributes={
                        str(position): _public_value(value)
                        for position, value in enumerate(getattr(item, "value_attributes", ()) or ())
                    },
                )
            )
        if not points:
            return
        matching = [
            snapshot
            for snapshot in self._subscriptions.values()
            if snapshot.state == Etp12SubscriptionState.ACTIVE
            and any(point.channel_id in snapshot.channel_ids.values() for point in points)
        ]
        for snapshot in matching:
            last_indexes = dict(snapshot.last_indexes)
            selected = tuple(
                point for point in points if point.channel_id in snapshot.channel_ids.values()
            )
            for point in selected:
                last_indexes[point.channel_id] = point.index
            updated = replace(snapshot, last_indexes=last_indexes)
            self._subscriptions[snapshot.definition.subscription_id] = updated
            batch = Etp12ChannelBatch(
                subscription_id=snapshot.definition.subscription_id,
                points=selected,
                received_at_utc=datetime.now(timezone.utc),
                message_id=message.header.message_id,
                correlation_id=message.header.correlation_id,
                protocol=Etp12Protocol(message.header.protocol),
            )
            for callback in tuple(self._channel_callbacks):
                result = callback(batch)
                if result is not None:
                    await result


def _parse_open_session(body: object) -> Etp12NegotiatedSession:
    protocols: list[Etp12SupportedProtocol] = []
    for item in getattr(body, "supported_protocols", ()) or ():
        try:
            protocol = Etp12Protocol(int(getattr(item, "protocol")))
        except (ValueError, TypeError):
            continue
        version = getattr(item, "protocol_version", None)
        protocols.append(
            Etp12SupportedProtocol(
                protocol=protocol,
                role=Etp12Role(str(_enum_value(getattr(item, "role"))).casefold()),
                protocol_version=(
                    int(getattr(version, "major", 1)),
                    int(getattr(version, "minor", 2)),
                    int(getattr(version, "revision", 0)),
                    int(getattr(version, "patch", 0)),
                ),
            )
        )
    objects = tuple(
        str(getattr(item, "qualified_type", item))
        for item in getattr(body, "supported_data_objects", ()) or ()
    )
    capabilities = _public_mapping(getattr(body, "endpoint_capabilities", {}))
    return Etp12NegotiatedSession(
        session_id=str(getattr(body, "session_id")),
        server_application_name=str(getattr(body, "application_name", "")),
        server_application_version=str(getattr(body, "application_version", "")),
        server_instance_id=str(getattr(body, "server_instance_id", "")),
        supported_protocols=tuple(protocols),
        supported_data_objects=objects,
        supported_formats=tuple(str(v) for v in getattr(body, "supported_formats", ()) or ()),
        supported_compression=_string_tuple(getattr(body, "supported_compression", ())),
        endpoint_capabilities=capabilities,
    )


def _enum_value(value: object) -> object:
    return getattr(value, "value", value)


def _string_tuple(value: object) -> tuple[str, ...]:
    if value is None:
        return ()
    if isinstance(value, str):
        return (value,) if value else ()
    try:
        return tuple(str(_enum_value(item)) for item in value)  # type: ignore[arg-type]
    except TypeError:
        return (str(_enum_value(value)),)


def _parse_resource(value: object) -> Etp12Resource:
    return Etp12Resource(
        uri=str(getattr(value, "uri", "")),
        name=str(getattr(value, "name", "")),
        data_object_type=str(getattr(value, "data_object_type", "")),
        source_count=_int_or_none(getattr(value, "source_count", None)),
        target_count=_int_or_none(getattr(value, "target_count", None)),
        store_created=_int_or_none(getattr(value, "store_created", None)),
        store_last_write=_int_or_none(getattr(value, "store_last_write", None)),
        active_status=_string_or_none(getattr(value, "active_status", None)),
        alternate_uris=tuple(str(v) for v in getattr(value, "alternate_uris", ()) or ()),
        custom_data=_public_mapping(getattr(value, "custom_data", {})),
    )


def _parse_array_identifier(key: str, value: object) -> Etp12DataArrayIdentifier:
    identifier = getattr(value, "uid", None) or getattr(value, "identifier", None) or value
    return Etp12DataArrayIdentifier(
        key=key,
        uri=str(getattr(identifier, "uri", "")),
        path_in_resource=str(getattr(identifier, "path_in_resource", key)),
    )


def _mapping_items(value: object):
    return value.items() if isinstance(value, Mapping) else ()


def _unwrap(value: object) -> object:
    if value is None:
        return None
    if hasattr(value, "item"):
        return _unwrap(getattr(value, "item"))
    if hasattr(value, "values"):
        return [_unwrap(item) for item in getattr(value, "values")]
    if isinstance(value, Mapping):
        return {str(k): _unwrap(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [_unwrap(item) for item in value]
    return value


def _public_value(value: object) -> object:
    unwrapped = _unwrap(value)
    if isinstance(unwrapped, (str, int, float, bool)) or unwrapped is None:
        return unwrapped
    return str(unwrapped)


def _public_mapping(value: object) -> dict[str, object]:
    if not isinstance(value, Mapping):
        return {}
    return {str(key): _public_value(item) for key, item in value.items()}


def _string_or_none(value: object) -> str | None:
    if value is None:
        return None
    return str(_unwrap(value))


def _int_or_none(value: object) -> int | None:
    if value is None:
        return None
    try:
        return int(_unwrap(value))
    except (TypeError, ValueError):
        return None
