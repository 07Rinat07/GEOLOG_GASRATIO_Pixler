from __future__ import annotations

from pathlib import Path

from geoworkbench.app.context import build_application_context
from geoworkbench.services.etp12_audit import JsonlEtp12AuditSink
from geoworkbench.services.etp12_credentials import WitsmlCredentialStoreAdapter
from geoworkbench.services.import_jobs import ImportSourceKind
from geoworkbench.services.mnemonic_registry import UserMnemonicRegistry
from geoworkbench.services.report_passport import ReportPassportBuilder
from geoworkbench.services.witsml1411_audit import InMemoryWitsml1411AuditSink
from geoworkbench.services.witsml_credentials import InMemoryWitsmlCredentialStore
from geoworkbench.storage.project_repository_router import ProjectRepositoryRouter


class _Settings:
    def value(self, _key: str, default: object = None) -> object:
        return default

    def setValue(self, _key: str, _value: object) -> None:
        return None

    def sync(self) -> None:
        return None


class _ImportPort:
    def __init__(self) -> None:
        self.executed: list[ImportSourceKind] = []
        self.unknown: list[str] = []

    def execute_import(self, kind: ImportSourceKind, source: Path | None = None) -> None:
        self.executed.append(kind)

    def report_unknown_source(self, selected_label: str) -> None:
        self.unknown.append(selected_label)


def _build_context(tmp_path: Path):
    mnemonic_registry = UserMnemonicRegistry(settings=_Settings())
    report_builder = ReportPassportBuilder()
    witsml_credentials = InMemoryWitsmlCredentialStore()
    etp12_credentials = WitsmlCredentialStoreAdapter(InMemoryWitsmlCredentialStore())
    witsml_audit = InMemoryWitsml1411AuditSink()
    etp12_audit = JsonlEtp12AuditSink(tmp_path / "etp12-test.jsonl", fsync=False)
    context = build_application_context(
        tmp_path,
        mnemonic_registry=mnemonic_registry,
        report_passport_builder=report_builder,
        witsml_credentials=witsml_credentials,
        etp12_credentials=etp12_credentials,
        witsml_audit=witsml_audit,
        etp12_audit=etp12_audit,
    )
    return (
        context,
        mnemonic_registry,
        report_builder,
        witsml_credentials,
        etp12_credentials,
        witsml_audit,
        etp12_audit,
    )


def test_application_context_keeps_process_wide_services(tmp_path: Path) -> None:
    (
        context,
        mnemonic_registry,
        report_builder,
        witsml_credentials,
        etp12_credentials,
        witsml_audit,
        etp12_audit,
    ) = _build_context(tmp_path)

    assert context.app_data_dir == tmp_path
    assert context.mnemonic_registry is mnemonic_registry
    assert context.report_passport_builder is report_builder
    assert context.witsml_credentials is witsml_credentials
    assert context.etp12_credentials is etp12_credentials
    assert context.witsml_audit is witsml_audit
    assert context.etp12_audit is etp12_audit


def test_project_scopes_do_not_share_mutable_session_state(tmp_path: Path) -> None:
    context, *_ = _build_context(tmp_path)

    first = context.create_project_scope()
    second = context.create_project_scope()

    assert first is not second
    assert first.project_controller is not second.project_controller
    assert first.session is not second.session
    assert isinstance(first.project_controller.repository, ProjectRepositoryRouter)
    assert isinstance(second.project_controller.repository, ProjectRepositoryRouter)
    assert first.project_controller.repository is not second.project_controller.repository


def test_import_controller_is_created_at_composition_boundary(tmp_path: Path) -> None:
    context, *_ = _build_context(tmp_path)
    port = _ImportPort()
    controller = context.create_import_job_controller(port)

    def localize(key: str) -> str:
        return key

    selected = dict(
        (choice.kind, choice.label) for choice in controller.choices(localize)
    )[ImportSourceKind.LAS]

    assert controller.dispatch(selected, True, localize) is True
    assert port.executed == [ImportSourceKind.LAS]
    assert port.unknown == []
