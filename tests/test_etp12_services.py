from __future__ import annotations

import asyncio
from dataclasses import dataclass
from pathlib import Path
from types import SimpleNamespace

import pytest

from geoworkbench.importers.etp12.models import (
    Etp12ConnectionProfile,
    Etp12DataArrayIdentifier,
    Etp12MessageHeader,
    Etp12Protocol,
    Etp12ReceivedMessage,
    Etp12SessionState,
    Etp12SubscriptionDefinition,
    Etp12SubscriptionState,
)
from geoworkbench.importers.etp12.service import Etp12ClientService
from geoworkbench.services.etp12_profiles import Etp12ProfileStore


class Body:
    def __init__(self, name: str, **kwargs) -> None:
        self._name = name
        for key, value in kwargs.items():
            setattr(self, key, value)

    @property
    def __class__(self):
        return type(self._name, (), {})


@dataclass
class NamedBody:
    name: str
    attrs: dict

    def __getattr__(self, item):
        if item == "__class__":
            return type(self.name, (), {})
        return self.attrs[item]


class FakeFactory:
    def request_session(self, profile): return SimpleNamespace(kind="request_session")
    def acknowledge(self): return SimpleNamespace(kind="ack")
    def close_session(self, reason): return SimpleNamespace(kind="close")
    def is_open_session(self, body): return getattr(body, "kind", "") == "open_session"
    def is_acknowledge(self, body): return False
    def is_protocol_exception(self, body): return False
    def protocol_exception_message(self, body): return ""
    def get_resources(self, **kwargs): return SimpleNamespace(kind="discover", kwargs=kwargs)
    def get_data_objects(self, uris, format="xml"): return SimpleNamespace(kind="objects", uris=uris)
    def data_array_identifier(self, uri, path_in_resource): return SimpleNamespace(uri=uri, path_in_resource=path_in_resource)
    def get_data_array_metadata(self, arrays): return SimpleNamespace(kind="array_meta", arrays=arrays)
    def get_data_arrays(self, arrays): return SimpleNamespace(kind="arrays", arrays=arrays)
    def get_channel_metadata(self, uris): return SimpleNamespace(kind="channel_meta", uris=uris)
    def channel_subscribe_info(self, **kwargs): return SimpleNamespace(**kwargs)
    def subscribe_channels(self, channels): return SimpleNamespace(kind="subscribe", channels=channels)
    def unsubscribe_channels(self, channel_ids): return SimpleNamespace(kind="unsubscribe", channel_ids=channel_ids)


class FakeEngine:
    def __init__(self) -> None:
        self.state = Etp12SessionState.DISCONNECTED
        self.sent_messages = 0
        self.received_messages = 0
        self.acknowledgements_sent = 0
        self.acknowledgements_received = 0
        self.pending_count = 0
        self.last_error = None
        self.handlers = []
        self.requested = []

    def add_unsolicited_handler(self, handler): self.handlers.append(handler)

    async def connect(self, profile, credentials):
        self.state = Etp12SessionState.OPEN
        version = SimpleNamespace(major=1, minor=2, revision=0, patch=0)
        protocols = [
            SimpleNamespace(protocol=value, role=role, protocol_version=version)
            for value, role in ((0, "server"), (3, "store"), (4, "store"), (9, "store"), (21, "store"))
        ]
        body = SimpleNamespace(
            kind="open_session",
            session_id="session-1",
            application_name="Fake Store",
            application_version="1",
            server_instance_id="server-1",
            supported_protocols=protocols,
            supported_data_objects=[SimpleNamespace(qualified_type="witsml21.*")],
            supported_formats=["xml"],
            supported_compression=[],
            endpoint_capabilities={},
        )
        return (Etp12ReceivedMessage(Etp12MessageHeader(0, 2, 2, 1, 2), body, "OpenSession"),)

    async def request(self, body, **kwargs):
        self.requested.append(body)
        kind = body.kind
        if kind == "discover":
            resource = SimpleNamespace(
                uri="eml:///witsml21.Well(1)", name="Well A", data_object_type="witsml21.Well",
                source_count=0, target_count=1, store_created=1, store_last_write=2,
                active_status="Active", alternate_uris=[], custom_data={}
            )
            response = SimpleNamespace(resources=[resource])
        elif kind == "objects":
            resource = SimpleNamespace(uri="u", name="n", data_object_type="witsml21.Well")
            response = SimpleNamespace(data_objects={"a": SimpleNamespace(resource=resource, format="xml", data=b"<x/>", blob_id=None)})
        elif kind == "array_meta":
            response = SimpleNamespace(array_metadata={"a": SimpleNamespace(dimensions=[2], transport_array_type="arrayOfDouble", logical_array_type="double", store_last_write=3)})
        elif kind == "arrays":
            response = SimpleNamespace(data_arrays={"a": SimpleNamespace(dimensions=[2], data=SimpleNamespace(values=[1.0, 2.0]))})
        elif kind == "channel_meta":
            index = SimpleNamespace(index_kind="Time", minimum_value=SimpleNamespace(item=1), maximum_value=SimpleNamespace(item=2))
            metadata = SimpleNamespace(id=42, uri="eml:///witsml21.Channel(42)", channel_name="ROP", data_kind="double", uom="m/h", indexes=[index], source="sensor", custom_data={})
            response = SimpleNamespace(metadata={"0": metadata})
        elif kind == "subscribe":
            response = SimpleNamespace(success={"0": "ok"})
        elif kind == "unsubscribe":
            response = SimpleNamespace(success={"0": "ok"})
        else:
            raise AssertionError(kind)
        return (Etp12ReceivedMessage(Etp12MessageHeader(3, 2, 4, 3, 2), response, type(response).__name__),)

    async def close(self, reason=""):
        self.state = Etp12SessionState.CLOSED


@pytest.fixture
def service():
    profile = Etp12ConnectionProfile(
        profile_id="test", name="Test", endpoint="ws://localhost:9002/etp",
        allow_insecure_localhost=True,
    )
    engines = []

    def factory():
        engine = FakeEngine()
        engines.append(engine)
        return engine, FakeFactory()

    value = Etp12ClientService(profile, engine_factory=factory)
    value._test_engines = engines
    return value


@pytest.mark.asyncio
async def test_discovery_store_and_data_array(service) -> None:
    negotiated = await service.connect()
    assert negotiated.supports(Etp12Protocol.DISCOVERY)
    resources = await service.discover("eml:///", data_object_types=["witsml21.Well"])
    assert resources[0].name == "Well A"
    objects = await service.get_data_objects({"a": "eml:///witsml21.Well(1)"})
    assert objects["a"].data == b"<x/>"
    ids = [Etp12DataArrayIdentifier("a", "eml:///witsml21.Channel(1)", "/values")]
    metadata = await service.get_data_array_metadata(ids)
    arrays = await service.get_data_arrays(ids)
    assert metadata["a"].dimensions == (2,)
    assert arrays["a"].values == [1.0, 2.0]
    await service.close()


@pytest.mark.asyncio
async def test_subscription_state_and_restore_after_reconnect(service) -> None:
    await service.connect()
    definition = Etp12SubscriptionDefinition(
        subscription_id="main",
        channel_uris=("eml:///witsml21.Channel(42)",),
    )
    first = await service.subscribe(definition)
    assert first.state == Etp12SubscriptionState.ACTIVE
    assert first.channel_ids[definition.channel_uris[0]] == 42
    second_session = await service.reconnect()
    assert second_session.session_id == "session-1"
    restored = service.snapshot().subscriptions[0]
    assert restored.state == Etp12SubscriptionState.ACTIVE
    assert restored.generation == 2
    assert len(service._test_engines) == 2
    await service.close()


@pytest.mark.asyncio
async def test_watchdog_reconnects_and_restores_subscription(service) -> None:
    await service.connect()
    definition = Etp12SubscriptionDefinition(
        subscription_id="watch",
        channel_uris=("eml:///witsml21.Channel(42)",),
    )
    await service.subscribe(definition)
    service._watchdog_interval_seconds = 0.01
    first_engine = service.engine
    assert first_engine is not None
    first_engine.last_error = "simulated transport failure"
    first_engine.state = Etp12SessionState.FAILED

    for _ in range(100):
        if len(service._test_engines) >= 2 and service.state == Etp12SessionState.OPEN:
            break
        await asyncio.sleep(0.01)

    assert len(service._test_engines) == 2
    restored = service.snapshot().subscriptions[0]
    assert restored.state == Etp12SubscriptionState.ACTIVE
    assert restored.generation == 2
    assert service.snapshot().generation == 2
    await service.close()


def test_profile_store_strict_and_secret_free(tmp_path: Path) -> None:
    store = Etp12ProfileStore(tmp_path / "profiles.json")
    profile = Etp12ConnectionProfile(
        profile_id="a", name="A", endpoint="wss://example.com/etp",
        username="reader", credential_id="etp-a",
    )
    store.upsert(profile)
    text = (tmp_path / "profiles.json").read_text(encoding="utf-8")
    assert "password" not in text.casefold()
    assert "secret" not in text.casefold()
    assert store.load_all() == (profile,)
