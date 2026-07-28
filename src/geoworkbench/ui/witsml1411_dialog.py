from __future__ import annotations

from pathlib import Path
from uuid import uuid4

from PySide6.QtCore import QStandardPaths, QThread, Qt, Signal
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QSpinBox,
    QTreeWidget,
    QTreeWidgetItem,
    QVBoxLayout,
    QWidget,
)

from geoworkbench.importers.witsml1411 import (
    Witsml1411AuthMode,
    Witsml1411ConnectionProfile,
    Witsml1411Credentials,
    Witsml1411LogHeader,
    Witsml1411ReadOnlyService,
    Witsml1411RetryPolicy,
    Witsml1411SoapClient,
    Witsml1411Well,
    Witsml1411Wellbore,
)
from geoworkbench.services.localization import AppLanguage, Localizer
from geoworkbench.services.witsml1411_audit import JsonlWitsml1411AuditSink
from geoworkbench.services.witsml1411_profiles import Witsml1411ProfileStore
from geoworkbench.services.witsml_credentials import (
    WitsmlCredentialStore,
    default_witsml_credential_store,
)
from geoworkbench.services.witsml_import_review import WitsmlImportCommit
from geoworkbench.ui.witsml_import_dialog import WitsmlImportDialog


class _TaskThread(QThread):
    succeeded = Signal(object)
    failed = Signal(str)

    def __init__(self, function, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.function = function

    def run(self) -> None:
        try:
            self.succeeded.emit(self.function())
        except Exception as exc:  # noqa: BLE001 - displayed to the operator
            self.failed.emit(str(exc))


class Witsml1411Dialog(QDialog):
    """Read-only WITSML 1.4.1.1 hierarchy browser and log importer."""

    def __init__(
        self,
        parent: QWidget | None = None,
        *,
        language: AppLanguage = AppLanguage.RU,
        profile_store: Witsml1411ProfileStore | None = None,
        credential_store: WitsmlCredentialStore | None = None,
    ) -> None:
        super().__init__(parent)
        self.localizer = Localizer.create(language)
        root_path = Path(
            QStandardPaths.writableLocation(QStandardPaths.StandardLocation.AppConfigLocation)
        )
        self.profile_store = profile_store or Witsml1411ProfileStore(
            root_path / "witsml1411" / "profiles.json"
        )
        self.credential_store = credential_store or default_witsml_credential_store()
        self.audit_path = root_path / "witsml1411" / "soap-audit.jsonl"
        self.service: Witsml1411ReadOnlyService | None = None
        self.accepted_commit: WitsmlImportCommit | None = None
        self._task: _TaskThread | None = None

        self.setWindowTitle(self._t("witsml1411.title"))
        self.resize(1050, 720)
        layout = QVBoxLayout(self)

        form = QFormLayout()
        self.profile_combo = QComboBox(self)
        self.endpoint = QLineEdit(self)
        self.username = QLineEdit(self)
        self.password = QLineEdit(self)
        self.password.setEchoMode(QLineEdit.EchoMode.Password)
        self.remember = QCheckBox(self._t("witsml1411.remember"), self)
        self.verify_tls = QCheckBox(self._t("witsml1411.verify_tls"), self)
        self.verify_tls.setChecked(True)
        self.timeout = QSpinBox(self)
        self.timeout.setRange(1, 600)
        self.timeout.setValue(20)
        self.attempts = QSpinBox(self)
        self.attempts.setRange(1, 10)
        self.attempts.setValue(3)
        form.addRow(self._t("witsml1411.profile"), self.profile_combo)
        form.addRow(self._t("witsml1411.endpoint"), self.endpoint)
        form.addRow(self._t("witsml1411.username"), self.username)
        form.addRow(self._t("witsml1411.password"), self.password)
        form.addRow("", self.remember)
        form.addRow("", self.verify_tls)
        form.addRow(self._t("witsml1411.timeout"), self.timeout)
        form.addRow(self._t("witsml1411.attempts"), self.attempts)
        layout.addLayout(form)

        controls = QHBoxLayout()
        self.connect_button = QPushButton(self._t("witsml1411.connect"), self)
        self.refresh_button = QPushButton(self._t("witsml1411.refresh"), self)
        self.refresh_button.setEnabled(False)
        self.import_button = QPushButton(self._t("witsml1411.import_log"), self)
        self.import_button.setEnabled(False)
        controls.addWidget(self.connect_button)
        controls.addWidget(self.refresh_button)
        controls.addWidget(self.import_button)
        controls.addStretch(1)
        layout.addLayout(controls)

        self.status = QLabel(self._t("witsml1411.disconnected"), self)
        self.status.setWordWrap(True)
        layout.addWidget(self.status)

        self.tree = QTreeWidget(self)
        self.tree.setHeaderLabels(
            [
                self._t("witsml1411.column_name"),
                self._t("witsml1411.column_type"),
                self._t("witsml1411.column_index"),
                self._t("witsml1411.column_range"),
            ]
        )
        self.tree.setAlternatingRowColors(True)
        layout.addWidget(self.tree, 1)

        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Close, self)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

        self.profile_combo.currentIndexChanged.connect(self._profile_selected)
        self.connect_button.clicked.connect(self._connect)
        self.refresh_button.clicked.connect(self._load_wells)
        self.import_button.clicked.connect(self._import_selected)
        self.tree.itemExpanded.connect(self._expanded)
        self.tree.currentItemChanged.connect(self._selection_changed)
        self._load_profiles()

    def _t(self, key: str, **kwargs: object) -> str:
        return self.localizer.text(key, **kwargs)

    def _load_profiles(self) -> None:
        self.profile_combo.blockSignals(True)
        self.profile_combo.clear()
        self.profile_combo.addItem(self._t("witsml1411.new_profile"), None)
        try:
            profiles = self.profile_store.load_all()
        except Exception as exc:  # noqa: BLE001
            profiles = ()
            self.status.setText(str(exc))
        for profile in profiles:
            self.profile_combo.addItem(profile.name, profile)
        self.profile_combo.blockSignals(False)
        self._profile_selected(0)

    def _profile_selected(self, _index: int) -> None:
        profile = self.profile_combo.currentData()
        if not isinstance(profile, Witsml1411ConnectionProfile):
            return
        self.endpoint.setText(profile.endpoint)
        self.username.setText(profile.username)
        self.verify_tls.setChecked(profile.verify_tls)
        self.timeout.setValue(round(profile.timeout_seconds))
        self.attempts.setValue(profile.retry.max_attempts)
        self.password.clear()
        if profile.credential_id:
            try:
                credentials = self.credential_store.load(profile.credential_id)
            except Exception as exc:  # noqa: BLE001
                self.status.setText(str(exc))
                credentials = None
            if credentials is not None:
                self.username.setText(credentials.username or profile.username)
                self.password.setText(credentials.password)
                self.remember.setChecked(True)

    def _profile_from_form(self) -> tuple[Witsml1411ConnectionProfile, Witsml1411Credentials]:
        existing = self.profile_combo.currentData()
        profile_id = (
            existing.profile_id
            if isinstance(existing, Witsml1411ConnectionProfile)
            else uuid4().hex
        )
        credential_id = f"witsml1411-{profile_id}"
        profile = Witsml1411ConnectionProfile(
            profile_id=profile_id,
            name=(existing.name if isinstance(existing, Witsml1411ConnectionProfile) else self.endpoint.text().strip()),
            endpoint=self.endpoint.text(),
            auth_mode=Witsml1411AuthMode.BASIC,
            username=self.username.text(),
            credential_id=credential_id,
            timeout_seconds=float(self.timeout.value()),
            verify_tls=self.verify_tls.isChecked(),
            retry=Witsml1411RetryPolicy(max_attempts=self.attempts.value()),
        )
        return profile, Witsml1411Credentials(self.username.text(), self.password.text())

    def _connect(self) -> None:
        try:
            profile, credentials = self._profile_from_form()
        except Exception as exc:  # noqa: BLE001
            QMessageBox.critical(self, self._t("witsml1411.title"), str(exc))
            return
        if self.remember.isChecked():
            try:
                self.profile_store.upsert(profile)
                self.credential_store.save(profile.credential_id or profile.profile_id, credentials)
            except Exception as exc:  # noqa: BLE001
                QMessageBox.warning(self, self._t("witsml1411.title"), str(exc))
        audit = JsonlWitsml1411AuditSink(self.audit_path)

        def task():
            service = Witsml1411ReadOnlyService(
                Witsml1411SoapClient(profile, credentials, audit=audit)
            )
            handshake = service.handshake()
            wells = service.list_wells()
            return service, handshake, wells

        self._start_task(task, self._connected)

    def _connected(self, result: object) -> None:
        service, handshake, wells = result
        self.service = service
        self.refresh_button.setEnabled(True)
        self.status.setText(
            self._t(
                "witsml1411.connected",
                version=handshake.selected_version,
                wells=len(wells),
            )
        )
        self._populate_wells(wells)
        self._load_profiles()

    def _load_wells(self) -> None:
        if self.service is None:
            return
        self._start_task(self.service.list_wells, self._populate_wells)

    def _populate_wells(self, wells: object) -> None:
        self.tree.clear()
        for well in wells:
            item = QTreeWidgetItem([well.name, "Well", "", well.field or ""])
            item.setData(0, Qt.ItemDataRole.UserRole, well)
            item.setChildIndicatorPolicy(QTreeWidgetItem.ChildIndicatorPolicy.ShowIndicator)
            self.tree.addTopLevelItem(item)
        self.tree.resizeColumnToContents(0)

    def _expanded(self, item: QTreeWidgetItem) -> None:
        if self.service is None or item.childCount() > 0:
            return
        value = item.data(0, Qt.ItemDataRole.UserRole)
        if isinstance(value, Witsml1411Well):
            self._start_task(
                lambda: self.service.list_wellbores(value.uid),
                lambda rows: self._populate_wellbores(item, rows),
            )
        elif isinstance(value, Witsml1411Wellbore):
            self._start_task(
                lambda: self.service.list_logs(value.uid_well, value.uid),
                lambda rows: self._populate_logs(item, rows),
            )

    def _populate_wellbores(self, parent: QTreeWidgetItem, rows: object) -> None:
        for value in rows:
            item = QTreeWidgetItem([value.name, "Wellbore", "", value.status or ""])
            item.setData(0, Qt.ItemDataRole.UserRole, value)
            item.setChildIndicatorPolicy(QTreeWidgetItem.ChildIndicatorPolicy.ShowIndicator)
            parent.addChild(item)

    def _populate_logs(self, parent: QTreeWidgetItem, rows: object) -> None:
        for value in rows:
            range_text = " — ".join(
                item for item in (value.start_index or value.start_datetime_index, value.end_index or value.end_datetime_index) if item
            )
            item = QTreeWidgetItem(
                [value.name, "Log", value.index_type or "", range_text]
            )
            item.setData(0, Qt.ItemDataRole.UserRole, value)
            parent.addChild(item)

    def _selection_changed(self, current: QTreeWidgetItem | None, _previous: QTreeWidgetItem | None) -> None:
        self.import_button.setEnabled(
            current is not None
            and isinstance(current.data(0, Qt.ItemDataRole.UserRole), Witsml1411LogHeader)
            and self._task is None
        )

    def _import_selected(self) -> None:
        item = self.tree.currentItem()
        log = item.data(0, Qt.ItemDataRole.UserRole) if item is not None else None
        if self.service is None or not isinstance(log, Witsml1411LogHeader):
            return
        self._start_task(
            lambda: self.service.fetch_log_package(log),
            self._review_package,
        )

    def _review_package(self, package: object) -> None:
        dialog = WitsmlImportDialog(
            parent=self,
            language=self.localizer.language,
            package=package,
        )
        if dialog.exec() == QDialog.DialogCode.Accepted and dialog.accepted_commit is not None:
            self.accepted_commit = dialog.accepted_commit
            self.accept()

    def _start_task(self, function, callback) -> None:
        if self._task is not None:
            return
        self.status.setText(self._t("witsml1411.working"))
        self.connect_button.setEnabled(False)
        self.refresh_button.setEnabled(False)
        self.import_button.setEnabled(False)
        task = _TaskThread(function, self)
        self._task = task

        def succeeded(value: object) -> None:
            self._finish_task()
            callback(value)

        task.succeeded.connect(succeeded)
        task.failed.connect(self._task_failed)
        task.finished.connect(task.deleteLater)
        task.start()

    def _finish_task(self) -> None:
        self._task = None
        self.connect_button.setEnabled(True)
        self.refresh_button.setEnabled(self.service is not None)
        self._selection_changed(self.tree.currentItem(), None)

    def _task_failed(self, message: str) -> None:
        self._finish_task()
        self.status.setText(message)
        QMessageBox.critical(self, self._t("witsml1411.title"), message)
