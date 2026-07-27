from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

from geoworkbench import __version__
from geoworkbench.importers.etp12.etpproto_adapter import _index_value
from geoworkbench.importers.etp12.models import Etp12MessageHeader
from geoworkbench.services.etp12_credentials import WindowsEtp12CredentialStore


ROOT = Path(__file__).resolve().parents[1]


class _IndexValue:
    def __init__(self, *, item):
        self.item = item


def test_channel_start_index_conversion() -> None:
    assert _index_value(_IndexValue, "42").item == 42
    assert _index_value(_IndexValue, "12.5").item == 12.5
    value = datetime(2026, 7, 27, 6, 30, tzinfo=timezone.utc)
    assert _index_value(_IndexValue, value).item == int(value.timestamp() * 1_000_000)
    assert _index_value(_IndexValue, "2026-07-27T06:30:00Z").item == int(
        value.timestamp() * 1_000_000
    )


def test_etp_header_flags_match_v12_contract() -> None:
    assert Etp12MessageHeader.MULTIPART == 0x01
    assert Etp12MessageHeader.FIN == 0x02
    assert Etp12MessageHeader.NO_DATA == 0x04
    assert Etp12MessageHeader.COMPRESSED == 0x08
    assert Etp12MessageHeader.ACK_REQUESTED == 0x10
    assert Etp12MessageHeader.EXTENSION == 0x20


def test_etp_credentials_have_separate_windows_namespace() -> None:
    assert WindowsEtp12CredentialStore._PREFIX.endswith("/ETP12/")
    assert "WITSML1411" not in WindowsEtp12CredentialStore._PREFIX


def test_packaging_and_ui_hooks_are_present() -> None:
    pyproject = (ROOT / "pyproject.toml").read_text(encoding="utf-8")
    assert f'version = "{__version__}"' in pyproject
    for requirement in ("websockets>=16", "fastavro>=1.9", "etptypes>=1.2", "etpproto>=1.0.7"):
        assert requirement in pyproject

    main_window = (ROOT / "src/geoworkbench/ui/main_window.py").read_text(encoding="utf-8")
    assert 'self._localized_action("shell.open_etp12")' in main_window
    assert "def open_etp12_session" in main_window

    dialog = (ROOT / "src/geoworkbench/ui/etp12_dialog.py").read_text(encoding="utf-8")
    assert "class _Etp12Worker(QThread)" in dialog
    assert "asyncio.run(self._main())" in dialog
    assert 'command == "subscribe"' in dialog
    assert "Etp12ImportReviewDialog" in dialog
    assert "Etp12AcquisitionRuntime" in dialog


def test_open_session_parser_accepts_enum_role_and_string_compression() -> None:
    from enum import Enum
    from types import SimpleNamespace

    from geoworkbench.importers.etp12.service import _parse_open_session

    class Role(Enum):
        STORE = "store"

    version = SimpleNamespace(major=1, minor=2, revision=0, patch=0)
    body = SimpleNamespace(
        session_id="s",
        application_name="server",
        application_version="1",
        server_instance_id="i",
        supported_protocols=[
            SimpleNamespace(protocol=0, role=Role.STORE, protocol_version=version)
        ],
        supported_data_objects=[],
        supported_formats=["xml"],
        supported_compression="gzip",
        endpoint_capabilities={},
    )
    parsed = _parse_open_session(body)
    assert parsed.supported_protocols[0].role.value == "store"
    assert parsed.supported_compression == ("gzip",)
