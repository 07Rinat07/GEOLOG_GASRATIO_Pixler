from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

from geoworkbench.project.controller import ProjectController
from geoworkbench.project.repository import ProjectRepository
from geoworkbench.project.session import ProjectSession
from geoworkbench.services.etp12_audit import JsonlEtp12AuditSink
from geoworkbench.services.etp12_credentials import (
    Etp12CredentialStore,
    default_etp12_credential_store,
)
from geoworkbench.services.import_jobs import ImportJobController, ImportJobPort
from geoworkbench.services.mnemonic_registry import UserMnemonicRegistry
from geoworkbench.services.report_passport import ReportPassportBuilder
from geoworkbench.services.witsml1411_audit import (
    JsonlWitsml1411AuditSink,
    Witsml1411AuditSink,
)
from geoworkbench.services.witsml_credentials import (
    WitsmlCredentialStore,
    default_witsml_credential_store,
)
from geoworkbench.storage.project_repository_router import ProjectRepositoryRouter


ProjectRepositoryFactory = Callable[[], ProjectRepository]


@dataclass(slots=True)
class ProjectScope:
    """Stateful project boundary created per project window/session."""

    project_controller: ProjectController

    @property
    def session(self) -> ProjectSession:
        return self.project_controller.session


@dataclass(slots=True)
class ApplicationContext:
    """Process-wide composition root for infrastructure and typed service factories.

    Stateful project services are deliberately created through ``create_project_scope``
    so a second project window cannot accidentally share mutable session state.
    """

    app_data_dir: Path
    mnemonic_registry: UserMnemonicRegistry
    report_passport_builder: ReportPassportBuilder
    witsml_credentials: WitsmlCredentialStore
    etp12_credentials: Etp12CredentialStore
    witsml_audit: Witsml1411AuditSink
    etp12_audit: JsonlEtp12AuditSink
    project_repository_factory: ProjectRepositoryFactory

    def create_project_scope(self) -> ProjectScope:
        repository = self.project_repository_factory()
        return ProjectScope(project_controller=ProjectController(repository=repository))

    @staticmethod
    def create_import_job_controller(port: ImportJobPort) -> ImportJobController:
        return ImportJobController(port)


def build_application_context(
    app_data_dir: str | Path,
    *,
    mnemonic_registry: UserMnemonicRegistry | None = None,
    report_passport_builder: ReportPassportBuilder | None = None,
    witsml_credentials: WitsmlCredentialStore | None = None,
    etp12_credentials: Etp12CredentialStore | None = None,
    witsml_audit: Witsml1411AuditSink | None = None,
    etp12_audit: JsonlEtp12AuditSink | None = None,
    project_repository_factory: ProjectRepositoryFactory = ProjectRepositoryRouter,
) -> ApplicationContext:
    """Build production infrastructure once at the application boundary."""

    root = Path(app_data_dir)
    audit_root = root / "audit"
    return ApplicationContext(
        app_data_dir=root,
        mnemonic_registry=mnemonic_registry or UserMnemonicRegistry(),
        report_passport_builder=report_passport_builder or ReportPassportBuilder(),
        witsml_credentials=witsml_credentials or default_witsml_credential_store(),
        etp12_credentials=etp12_credentials or default_etp12_credential_store(),
        witsml_audit=witsml_audit or JsonlWitsml1411AuditSink(audit_root / "witsml1411.jsonl"),
        etp12_audit=etp12_audit or JsonlEtp12AuditSink(audit_root / "etp12.jsonl"),
        project_repository_factory=project_repository_factory,
    )
