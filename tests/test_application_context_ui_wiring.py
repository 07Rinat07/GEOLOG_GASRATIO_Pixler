from __future__ import annotations

from pathlib import Path

from geoworkbench.app.context import build_application_context
from geoworkbench.services.etp12_credentials import WitsmlCredentialStoreAdapter
from geoworkbench.services.etp12_profiles import Etp12ProfileStore
from geoworkbench.services.mnemonic_registry import UserMnemonicRegistry
from geoworkbench.services.report_passport import ReportPassportBuilder
from geoworkbench.services.witsml1411_audit import InMemoryWitsml1411AuditSink
from geoworkbench.services.witsml1411_profiles import Witsml1411ProfileStore
from geoworkbench.services.witsml_credentials import InMemoryWitsmlCredentialStore
from geoworkbench.storage.project_codec import ProjectDocument
from geoworkbench.ui.etp12_dialog import Etp12Dialog
from geoworkbench.ui.main_window_drilling import MainWindow
from geoworkbench.ui.witsml1411_dialog import Witsml1411Dialog


class _Settings:
    def value(self, _key: str, default: object = None) -> object:
        return default

    def setValue(self, _key: str, _value: object) -> None:
        return None

    def sync(self) -> None:
        return None


class _Repository:
    def load(self, source: Path) -> ProjectDocument:
        raise AssertionError(f"Unexpected load: {source}")

    def save(self, document: ProjectDocument, target: Path) -> None:
        del document
        raise AssertionError(f"Unexpected save: {target}")


class _EtpAuditSink:
    def __init__(self) -> None:
        self.events: list[object] = []

    def record(self, event: object) -> None:
        self.events.append(event)


def _context(tmp_path: Path):
    repository = _Repository()
    mnemonic_registry = UserMnemonicRegistry(settings=_Settings())
    report_builder = ReportPassportBuilder()
    witsml_credentials = InMemoryWitsmlCredentialStore()
    etp12_credentials = WitsmlCredentialStoreAdapter(InMemoryWitsmlCredentialStore())
    witsml_audit = InMemoryWitsml1411AuditSink()
    etp12_audit = _EtpAuditSink()
    context = build_application_context(
        tmp_path,
        mnemonic_registry=mnemonic_registry,
        report_passport_builder=report_builder,
        witsml_credentials=witsml_credentials,
        etp12_credentials=etp12_credentials,
        witsml_audit=witsml_audit,
        etp12_audit=etp12_audit,
        project_repository_factory=lambda: repository,
    )
    return (
        context,
        repository,
        mnemonic_registry,
        report_builder,
        witsml_credentials,
        etp12_credentials,
        witsml_audit,
        etp12_audit,
    )


def test_production_main_window_consumes_application_context(qapp, tmp_path: Path) -> None:
    (
        context,
        repository,
        mnemonic_registry,
        report_builder,
        _witsml_credentials,
        _etp12_credentials,
        _witsml_audit,
        _etp12_audit,
    ) = _context(tmp_path)

    window = MainWindow(application_context=context)
    try:
        assert window.application_context is context
        assert window.mnemonic_registry is mnemonic_registry
        assert window.project_controller.repository is repository
        assert window.report_passport_builder is report_builder
    finally:
        window.close()


def test_witsml_dialog_uses_injected_credentials_and_audit(qapp, tmp_path: Path) -> None:
    context, *_ = _context(tmp_path)
    dialog = Witsml1411Dialog(
        profile_store=Witsml1411ProfileStore(tmp_path / "witsml-profiles.json"),
        credential_store=context.witsml_credentials,
        audit_sink=context.witsml_audit,
    )
    try:
        assert dialog.credential_store is context.witsml_credentials
        assert dialog.audit_sink is context.witsml_audit
    finally:
        dialog.close()


def test_etp_dialog_uses_injected_credentials_and_audit(qapp, tmp_path: Path) -> None:
    context, *_ = _context(tmp_path)
    dialog = Etp12Dialog(
        profile_store=Etp12ProfileStore(tmp_path / "etp-profiles.json"),
        credential_store=context.etp12_credentials,
        audit_sink=context.etp12_audit,
    )
    try:
        assert dialog.credential_store is context.etp12_credentials
        assert dialog.audit_sink is context.etp12_audit
        assert dialog.worker.audit_sink is context.etp12_audit
    finally:
        dialog.close()
