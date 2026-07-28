from __future__ import annotations

import asyncio
from dataclasses import dataclass
from pathlib import Path
from queue import Queue
from typing import Callable, Mapping, TYPE_CHECKING
from uuid import uuid4

from PySide6.QtCore import QStandardPaths, QThread, Qt, Signal
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPlainTextEdit,
    QPushButton,
    QSpinBox,
    QSplitter,
    QTableWidget,
    QTableWidgetItem,
    QTreeWidget,
    QTreeWidgetItem,
    QVBoxLayout,
    QWidget,
)

from geoworkbench.importers.etp12 import (
    Etp12AuthMode,
    Etp12ChannelBatch,
    Etp12ChannelMetadata,
    Etp12ClientService,
    Etp12ConnectionProfile,
    Etp12Credentials,
    Etp12DataArray,
    Etp12DataArrayIdentifier,
    Etp12DataObject,
    Etp12NegotiatedSession,
    Etp12Resource,
    Etp12SessionSnapshot,
    Etp12SubscriptionDefinition,
    Etp12SubscriptionSnapshot,
)
from geoworkbench.services.etp12_audit import JsonlEtp12AuditSink
from geoworkbench.services.etp12_credentials import (
    Etp12CredentialStore,
    default_etp12_credential_store,
)
from geoworkbench.services.etp12_profiles import Etp12ProfileStore
from geoworkbench.services.etp12_import_review import (
    Etp12DiscoveryAccumulator,
    Etp12ImportReviewCommit,
    restore_etp12_import_review_commit,
)
from geoworkbench.services.etp12_acquisition import (
    Etp12AcquisitionConfig,
    Etp12AcquisitionRuntime,
    Etp12AcquisitionState,
    Etp12BackpressurePolicy,
    open_etp12_sessions,
)
from geoworkbench.services.localization import AppLanguage, Localizer
from geoworkbench.ui.etp12_import_review_dialog import Etp12ImportReviewDialog

if TYPE_CHECKING:
    from geoworkbench.domain.models import Well


@dataclass(frozen=True, slots=True)
class _Etp12ConnectRequest:
    profile: Etp12ConnectionProfile
    credentials: Etp12Credentials


@dataclass(frozen=True, slots=True)
class _Etp12DiscoveryRequest:
    uri: str
    depth: int
    data_object_types: tuple[str, ...]
    scope: str
    include_edges: bool


def _channel_uri_payload(payload: object) -> tuple[str, ...]:
    if not isinstance(payload, tuple):
        raise TypeError("ETP channel URI payload must be a tuple")
    uris: list[str] = []
    for item in payload:
        if not isinstance(item, str):
            raise TypeError("ETP channel URI payload must contain strings")
        uris.append(item)
    return tuple(uris)


class _Etp12Worker(QThread):
    connected = Signal(object)
    resources = Signal(object)
    object_received = Signal(object)
    array_received = Signal(object)
    channel_metadata = Signal(object)
    subscription = Signal(object)
    channel_batch = Signal(object)
    snapshot = Signal(object)
    failed = Signal(str)
    stopped = Signal()

    def __init__(self, audit_path: Path, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.audit_path = audit_path
        self.commands: Queue[tuple[str, object]] = Queue()
        self._service: Etp12ClientService | None = None
        self._running = True

    def submit(self, command: str, payload: object = None) -> None:
        self.commands.put((command, payload))

    def run(self) -> None:
        asyncio.run(self._main())

    async def _main(self) -> None:
        while self._running:
            command, payload = await asyncio.to_thread(self.commands.get)
            try:
                if command == "connect":
                    if not isinstance(payload, _Etp12ConnectRequest):
                        raise TypeError("ETP connect command requires a typed request")
                    if self._service is not None:
                        await self._service.close()
                    audit = JsonlEtp12AuditSink(self.audit_path)
                    service = Etp12ClientService(
                        payload.profile,
                        payload.credentials,
                        audit=audit.record,
                    )
                    service.add_channel_callback(self._on_channel_batch)
                    negotiated = await service.connect()
                    self._service = service
                    self.connected.emit(negotiated)
                    self.snapshot.emit(service.snapshot())
                elif command == "reconnect":
                    service = self._require_service()
                    negotiated = await service.reconnect()
                    self.connected.emit(negotiated)
                    self.snapshot.emit(service.snapshot())
                elif command == "discover":
                    if not isinstance(payload, _Etp12DiscoveryRequest):
                        raise TypeError("ETP discover command requires a typed request")
                    service = self._require_service()
                    resources = await service.discover(
                        payload.uri,
                        depth=payload.depth,
                        data_object_types=payload.data_object_types,
                        scope=payload.scope,
                        include_edges=payload.include_edges,
                    )
                    self.resources.emit(resources)
                    self.snapshot.emit(service.snapshot())
                elif command == "get_object":
                    if not isinstance(payload, str):
                        raise TypeError("ETP object command requires a URI string")
                    service = self._require_service()
                    objects = await service.get_data_objects({"selected": payload})
                    self.object_received.emit(objects.get("selected"))
                    self.snapshot.emit(service.snapshot())
                elif command == "get_array":
                    if not isinstance(payload, Etp12DataArrayIdentifier):
                        raise TypeError("ETP array command requires an array identifier")
                    service = self._require_service()
                    identifier = payload
                    arrays = await service.get_data_arrays([identifier])
                    self.array_received.emit(arrays.get(identifier.key))
                    self.snapshot.emit(service.snapshot())
                elif command == "metadata":
                    service = self._require_service()
                    uris = _channel_uri_payload(payload)
                    metadata = await service.get_channel_metadata(
                        {str(index): uri for index, uri in enumerate(uris)}
                    )
                    self.channel_metadata.emit(metadata)
                    self.snapshot.emit(service.snapshot())
                elif command == "subscribe":
                    if not isinstance(payload, Etp12SubscriptionDefinition):
                        raise TypeError("ETP subscribe command requires a subscription definition")
                    service = self._require_service()
                    definition = payload
                    metadata = await service.get_channel_metadata(
                        {str(index): uri for index, uri in enumerate(definition.channel_uris)}
                    )
                    self.channel_metadata.emit(metadata)
                    subscription = await service.subscribe(definition)
                    self.snapshot.emit(service.snapshot())
                    self.subscription.emit(subscription)
                elif command == "unsubscribe":
                    if not isinstance(payload, str):
                        raise TypeError("ETP unsubscribe command requires a subscription id")
                    service = self._require_service()
                    await service.unsubscribe(payload)
                    self.snapshot.emit(service.snapshot())
                elif command == "close":
                    if self._service is not None:
                        await self._service.close()
                        self.snapshot.emit(self._service.snapshot())
                elif command == "stop":
                    self._running = False
                    if self._service is not None:
                        await self._service.close()
                    break
                else:
                    raise ValueError(f"Unsupported ETP worker command: {command}")
            except Exception as exc:  # noqa: BLE001 - displayed to operator
                self.failed.emit(str(exc))
                if self._service is not None:
                    self.snapshot.emit(self._service.snapshot())
        self.stopped.emit()

    async def _on_channel_batch(self, batch: Etp12ChannelBatch) -> None:
        self.channel_batch.emit(batch)
        if self._service is not None:
            self.snapshot.emit(self._service.snapshot())

    def _require_service(self) -> Etp12ClientService:
        if self._service is None:
            raise RuntimeError("ETP session is not connected")
        return self._service


class Etp12Dialog(QDialog):
    """ETP v1.2 Discovery/Store/Data Array browser and channel subscriber."""

    def __init__(
        self,
        parent: QWidget | None = None,
        *,
        language: AppLanguage = AppLanguage.RU,
        profile_store: Etp12ProfileStore | None = None,
        credential_store: Etp12CredentialStore | None = None,
        well_provider: Callable[[], "Well | None"] | None = None,
        on_dataset_changed: Callable[[str], None] | None = None,
    ) -> None:
        super().__init__(parent)
        self.localizer = Localizer.create(language)
        root = Path(QStandardPaths.writableLocation(QStandardPaths.StandardLocation.AppConfigLocation))
        self.profile_store = profile_store or Etp12ProfileStore(root / "etp12" / "profiles.json")
        self.credential_store = credential_store or default_etp12_credential_store()
        self.worker = _Etp12Worker(root / "etp12" / "audit.jsonl", self)
        self._connected = False
        self._latest_channel_values: dict[int, tuple[object, object]] = {}
        self.well_provider = well_provider
        self.on_dataset_changed = on_dataset_changed
        self.discovery = Etp12DiscoveryAccumulator()
        self.channel_metadata_by_uri: dict[str, Etp12ChannelMetadata] = {}
        self.review_commit: Etp12ImportReviewCommit | None = None
        self.acquisition_runtime: Etp12AcquisitionRuntime | None = None

        self.setWindowTitle(self._t("etp12.title"))
        self.resize(1180, 820)
        root_layout = QVBoxLayout(self)

        connection_box = QGroupBox(self._t("etp12.connection"), self)
        connection_form = QFormLayout(connection_box)
        self.profile_combo = QComboBox(connection_box)
        self.endpoint = QLineEdit("wss://localhost:9002/etp", connection_box)
        self.auth_mode = QComboBox(connection_box)
        for mode in Etp12AuthMode:
            self.auth_mode.addItem(mode.value, mode)
        self.username = QLineEdit(connection_box)
        self.secret = QLineEdit(connection_box)
        self.secret.setEchoMode(QLineEdit.EchoMode.Password)
        self.remember = QCheckBox(self._t("etp12.remember"), connection_box)
        self.verify_tls = QCheckBox(self._t("etp12.verify_tls"), connection_box)
        self.verify_tls.setChecked(True)
        self.allow_local_ws = QCheckBox(self._t("etp12.allow_local_ws"), connection_box)
        self.timeout = QSpinBox(connection_box)
        self.timeout.setRange(5, 600)
        self.timeout.setValue(30)
        self.max_message_mb = QSpinBox(connection_box)
        self.max_message_mb.setRange(1, 512)
        self.max_message_mb.setValue(16)
        self.max_multipart_mb = QSpinBox(connection_box)
        self.max_multipart_mb.setRange(1, 4096)
        self.max_multipart_mb.setValue(64)
        self.max_multipart_parts = QSpinBox(connection_box)
        self.max_multipart_parts.setRange(1, 100_000)
        self.max_multipart_parts.setValue(256)
        self.multipart_timeout = QSpinBox(connection_box)
        self.multipart_timeout.setRange(1, 3600)
        self.multipart_timeout.setValue(30)
        connection_form.addRow(self._t("etp12.profile"), self.profile_combo)
        connection_form.addRow(self._t("etp12.endpoint"), self.endpoint)
        connection_form.addRow(self._t("etp12.auth"), self.auth_mode)
        connection_form.addRow(self._t("etp12.username"), self.username)
        connection_form.addRow(self._t("etp12.secret"), self.secret)
        connection_form.addRow("", self.remember)
        connection_form.addRow("", self.verify_tls)
        connection_form.addRow("", self.allow_local_ws)
        connection_form.addRow(self._t("etp12.timeout"), self.timeout)
        connection_form.addRow(self._t("etp12.max_message"), self.max_message_mb)
        connection_form.addRow(self._t("etp12.max_multipart"), self.max_multipart_mb)
        connection_form.addRow(self._t("etp12.max_multipart_parts"), self.max_multipart_parts)
        connection_form.addRow(self._t("etp12.multipart_timeout"), self.multipart_timeout)
        root_layout.addWidget(connection_box)

        connection_buttons = QHBoxLayout()
        self.connect_button = QPushButton(self._t("etp12.connect"), self)
        self.reconnect_button = QPushButton(self._t("etp12.reconnect"), self)
        self.disconnect_button = QPushButton(self._t("etp12.disconnect"), self)
        self.reconnect_button.setEnabled(False)
        self.disconnect_button.setEnabled(False)
        connection_buttons.addWidget(self.connect_button)
        connection_buttons.addWidget(self.reconnect_button)
        connection_buttons.addWidget(self.disconnect_button)
        connection_buttons.addStretch(1)
        root_layout.addLayout(connection_buttons)

        self.status = QLabel(self._t("etp12.disconnected"), self)
        self.status.setWordWrap(True)
        root_layout.addWidget(self.status)

        splitter = QSplitter(Qt.Orientation.Horizontal, self)
        left = QWidget(splitter)
        left_layout = QVBoxLayout(left)
        discovery_form = QFormLayout()
        self.discovery_uri = QLineEdit("eml:///", left)
        self.object_type = QLineEdit("witsml21.*", left)
        discovery_form.addRow(self._t("etp12.discovery_uri"), self.discovery_uri)
        discovery_form.addRow(self._t("etp12.object_type"), self.object_type)
        left_layout.addLayout(discovery_form)
        self.discover_button = QPushButton(self._t("etp12.discover"), left)
        self.get_object_button = QPushButton(self._t("etp12.get_object"), left)
        self.discover_button.setEnabled(False)
        self.get_object_button.setEnabled(False)
        discovery_buttons = QHBoxLayout()
        discovery_buttons.addWidget(self.discover_button)
        discovery_buttons.addWidget(self.get_object_button)
        left_layout.addLayout(discovery_buttons)
        self.tree = QTreeWidget(left)
        self.tree.setHeaderLabels([
            self._t("etp12.column_name"),
            self._t("etp12.column_type"),
            self._t("etp12.column_uri"),
        ])
        left_layout.addWidget(self.tree, 1)

        array_box = QGroupBox(self._t("etp12.data_array"), left)
        array_form = QFormLayout(array_box)
        self.array_uri = QLineEdit(array_box)
        self.array_path = QLineEdit(array_box)
        self.array_button = QPushButton(self._t("etp12.get_array"), array_box)
        self.array_button.setEnabled(False)
        array_form.addRow(self._t("etp12.array_uri"), self.array_uri)
        array_form.addRow(self._t("etp12.array_path"), self.array_path)
        array_form.addRow("", self.array_button)
        left_layout.addWidget(array_box)

        right = QWidget(splitter)
        right_layout = QVBoxLayout(right)
        channel_box = QGroupBox(self._t("etp12.channels"), right)
        channel_layout = QVBoxLayout(channel_box)
        self.channel_uris = QPlainTextEdit(channel_box)
        self.channel_uris.setPlaceholderText("eml:///witsml21.Channel(...)")
        channel_layout.addWidget(self.channel_uris)
        channel_buttons = QHBoxLayout()
        self.metadata_button = QPushButton(self._t("etp12.metadata"), channel_box)
        self.subscribe_button = QPushButton(self._t("etp12.subscribe"), channel_box)
        self.unsubscribe_button = QPushButton(self._t("etp12.unsubscribe"), channel_box)
        for button in (self.metadata_button, self.subscribe_button, self.unsubscribe_button):
            button.setEnabled(False)
            channel_buttons.addWidget(button)
        channel_layout.addLayout(channel_buttons)
        acquisition_buttons = QHBoxLayout()
        self.review_button = QPushButton(self._t("etp12.review_action"), channel_box)
        self.start_acquisition_button = QPushButton(
            self._t("etp12.acquisition_start"), channel_box
        )
        self.flush_acquisition_button = QPushButton(
            self._t("etp12.acquisition_flush"), channel_box
        )
        self.close_acquisition_button = QPushButton(
            self._t("etp12.acquisition_close"), channel_box
        )
        for button in (
            self.review_button,
            self.start_acquisition_button,
            self.flush_acquisition_button,
            self.close_acquisition_button,
        ):
            acquisition_buttons.addWidget(button)
        channel_layout.addLayout(acquisition_buttons)
        right_layout.addWidget(channel_box)

        self.channel_table = QTableWidget(0, 5, right)
        self.channel_table.setHorizontalHeaderLabels([
            self._t("etp12.channel_id"), self._t("etp12.channel_name"),
            self._t("etp12.uom"), self._t("etp12.index"), self._t("etp12.value"),
        ])
        right_layout.addWidget(self.channel_table, 1)
        self.details = QPlainTextEdit(right)
        self.details.setReadOnly(True)
        right_layout.addWidget(self.details, 1)
        splitter.addWidget(left)
        splitter.addWidget(right)
        splitter.setSizes([560, 620])
        root_layout.addWidget(splitter, 1)

        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Close, self)
        buttons.rejected.connect(self.close)
        root_layout.addWidget(buttons)

        self.connect_button.clicked.connect(self._connect)
        self.reconnect_button.clicked.connect(lambda: self.worker.submit("reconnect"))
        self.disconnect_button.clicked.connect(lambda: self.worker.submit("close"))
        self.discover_button.clicked.connect(self._discover)
        self.get_object_button.clicked.connect(self._get_object)
        self.array_button.clicked.connect(self._get_array)
        self.metadata_button.clicked.connect(lambda: self.worker.submit("metadata", self._channel_uri_list()))
        self.subscribe_button.clicked.connect(self._subscribe)
        self.unsubscribe_button.clicked.connect(lambda: self.worker.submit("unsubscribe", "ui-main"))
        self.review_button.clicked.connect(self._review_import)
        self.start_acquisition_button.clicked.connect(self._start_acquisition)
        self.flush_acquisition_button.clicked.connect(self._flush_acquisition)
        self.close_acquisition_button.clicked.connect(self._close_acquisition)
        self.tree.currentItemChanged.connect(self._tree_selection)
        self.profile_combo.currentIndexChanged.connect(self._profile_selected)

        self.worker.connected.connect(self._on_connected)
        self.worker.resources.connect(self._on_resources)
        self.worker.object_received.connect(self._on_object)
        self.worker.array_received.connect(self._on_array)
        self.worker.channel_metadata.connect(self._on_metadata)
        self.worker.subscription.connect(self._on_subscription)
        self.worker.channel_batch.connect(self._on_channel_batch)
        self.worker.snapshot.connect(self._on_snapshot)
        self.worker.failed.connect(self._on_failed)
        self.worker.start()
        self._load_profiles()
        self._refresh_acquisition_controls()

    def _t(self, key: str, **kwargs: object) -> str:
        return self.localizer.text(key, **kwargs)

    def _reject_worker_payload(self, label: str, value: object) -> None:
        message = f"Unexpected ETP {label} payload: {type(value).__name__}"
        self.status.setText(message)
        self.details.appendPlainText(message)

    def _load_profiles(self) -> None:
        self.profile_combo.blockSignals(True)
        self.profile_combo.clear()
        self.profile_combo.addItem(self._t("etp12.new_profile"), None)
        try:
            for profile in self.profile_store.load_all():
                self.profile_combo.addItem(profile.name, profile)
        except Exception as exc:  # noqa: BLE001
            self.status.setText(str(exc))
        self.profile_combo.blockSignals(False)

    def _profile_selected(self, _index: int) -> None:
        profile = self.profile_combo.currentData()
        if not isinstance(profile, Etp12ConnectionProfile):
            return
        self.endpoint.setText(profile.endpoint)
        self.username.setText(profile.username)
        self.auth_mode.setCurrentIndex(max(0, self.auth_mode.findData(profile.auth_mode)))
        self.verify_tls.setChecked(profile.verify_tls)
        self.allow_local_ws.setChecked(profile.allow_insecure_localhost)
        self.timeout.setValue(round(profile.request_timeout_seconds))
        self.max_message_mb.setValue(max(1, profile.max_message_bytes // (1024 * 1024)))
        self.max_multipart_mb.setValue(
            max(1, profile.max_multipart_bytes // (1024 * 1024))
        )
        self.max_multipart_parts.setValue(profile.max_multipart_parts)
        self.multipart_timeout.setValue(round(profile.multipart_timeout_seconds))
        self.secret.clear()
        if profile.credential_id:
            try:
                credentials = self.credential_store.load(profile.credential_id)
            except Exception as exc:  # noqa: BLE001
                self.status.setText(str(exc))
                credentials = None
            if credentials is not None:
                self.username.setText(credentials.username or profile.username)
                self.secret.setText(credentials.secret)
                self.remember.setChecked(True)

    def _form_values(self) -> tuple[Etp12ConnectionProfile, Etp12Credentials]:
        existing = self.profile_combo.currentData()
        profile_id = existing.profile_id if isinstance(existing, Etp12ConnectionProfile) else uuid4().hex
        credential_id = f"etp12-{profile_id}"
        profile = Etp12ConnectionProfile(
            profile_id=profile_id,
            name=(existing.name if isinstance(existing, Etp12ConnectionProfile) else self.endpoint.text().strip()),
            endpoint=self.endpoint.text(),
            auth_mode=self.auth_mode.currentData(),
            username=self.username.text(),
            credential_id=credential_id,
            verify_tls=self.verify_tls.isChecked(),
            allow_insecure_localhost=self.allow_local_ws.isChecked(),
            request_timeout_seconds=float(self.timeout.value()),
            max_message_bytes=self.max_message_mb.value() * 1024 * 1024,
            max_multipart_bytes=self.max_multipart_mb.value() * 1024 * 1024,
            max_multipart_parts=self.max_multipart_parts.value(),
            multipart_timeout_seconds=float(self.multipart_timeout.value()),
        )
        return profile, Etp12Credentials(self.username.text(), self.secret.text())

    def _connect(self) -> None:
        try:
            profile, credentials = self._form_values()
            if self.remember.isChecked():
                self.profile_store.upsert(profile)
                self.credential_store.save(profile.credential_id or profile.profile_id, credentials)
        except Exception as exc:  # noqa: BLE001
            QMessageBox.critical(self, self._t("etp12.title"), str(exc))
            return
        self.status.setText(self._t("etp12.connecting"))
        self.worker.submit("connect", _Etp12ConnectRequest(profile, credentials))

    def _discover(self) -> None:
        types = tuple(value.strip() for value in self.object_type.text().split(",") if value.strip())
        self.worker.submit(
            "discover",
            _Etp12DiscoveryRequest(
                uri=self.discovery_uri.text().strip(),
                depth=1,
                data_object_types=types,
                scope="targetsOrSelf",
                include_edges=False,
            ),
        )

    def _get_object(self) -> None:
        item = self.tree.currentItem()
        resource = item.data(0, Qt.ItemDataRole.UserRole) if item is not None else None
        if isinstance(resource, Etp12Resource):
            self.worker.submit("get_object", resource.uri)

    def _get_array(self) -> None:
        identifier = Etp12DataArrayIdentifier(
            key="ui-array",
            uri=self.array_uri.text().strip(),
            path_in_resource=self.array_path.text().strip(),
        )
        self.worker.submit("get_array", identifier)

    def _subscribe(self) -> None:
        try:
            definition = Etp12SubscriptionDefinition(
                subscription_id="ui-main",
                channel_uris=self._channel_uri_list(),
            )
        except Exception as exc:  # noqa: BLE001
            QMessageBox.warning(self, self._t("etp12.title"), str(exc))
            return
        self.worker.submit("subscribe", definition)

    def _channel_uri_list(self) -> tuple[str, ...]:
        return tuple(line.strip() for line in self.channel_uris.toPlainText().splitlines() if line.strip())

    def _on_connected(self, value: object) -> None:
        if not isinstance(value, Etp12NegotiatedSession):
            self._reject_worker_payload("negotiated-session", value)
            return
        self._connected = True
        self.status.setText(self._t(
            "etp12.connected",
            server=value.server_application_name,
            version=value.server_application_version,
            protocols=", ".join(str(item.protocol.value) for item in value.supported_protocols),
        ))
        self._set_connected_controls(True)
        self._load_profiles()

    def _on_resources(self, values: object) -> None:
        if not isinstance(values, tuple) or not all(
            isinstance(value, Etp12Resource) for value in values
        ):
            self._reject_worker_payload("resources", values)
            return
        resources = tuple(
            value for value in values if isinstance(value, Etp12Resource)
        )
        self.tree.clear()
        for resource in resources:
            item = QTreeWidgetItem([resource.name, resource.data_object_type, resource.uri])
            item.setData(0, Qt.ItemDataRole.UserRole, resource)
            self.tree.addTopLevelItem(item)
        self.tree.resizeColumnToContents(0)
        self.details.setPlainText(self._t("etp12.resources_count", count=len(resources)))

    def _on_object(self, value: object) -> None:
        if value is None:
            self.details.setPlainText(self._t("etp12.object_missing"))
            return
        if not isinstance(value, Etp12DataObject):
            self._reject_worker_payload("data-object", value)
            return
        preview = value.data[:4000].decode("utf-8", errors="replace")
        self.details.setPlainText(
            f"URI: {value.uri}\nFormat: {value.format}\nBytes: {len(value.data)}\n\n{preview}"
        )

    def _on_array(self, value: object) -> None:
        if value is None:
            self.details.setPlainText(self._t("etp12.array_missing"))
            return
        if not isinstance(value, Etp12DataArray):
            self._reject_worker_payload("data-array", value)
            return
        self.details.setPlainText(
            f"Array: {value.identifier.uri} {value.identifier.path_in_resource}\n"
            f"Dimensions: {value.dimensions}\nValues: {str(value.values)[:4000]}"
        )

    def _on_metadata(self, values: object) -> None:
        if not isinstance(values, Mapping):
            self._reject_worker_payload("channel-metadata", values)
            return
        rows: list[Etp12ChannelMetadata] = []
        for value in values.values():
            if not isinstance(value, Etp12ChannelMetadata):
                self._reject_worker_payload("channel-metadata", value)
                return
            rows.append(value)
        if rows:
            self.channel_metadata_by_uri = {value.channel_uri: value for value in rows}
            self.discovery.update_metadata(rows)
            if self.acquisition_runtime is not None:
                self.acquisition_runtime.update_metadata(rows)
            else:
                self._restore_open_acquisition_session()
        self.channel_table.setRowCount(len(rows))
        for row, value in enumerate(rows):
            for column, text in enumerate((
                value.channel_id, value.channel_name, value.uom or "", value.index_kind or "", ""
            )):
                self.channel_table.setItem(row, column, QTableWidgetItem(str(text)))
        self._refresh_acquisition_controls()

    def _on_subscription(self, value: object) -> None:
        if not isinstance(value, Etp12SubscriptionSnapshot):
            self._reject_worker_payload("subscription", value)
            return
        self.details.appendPlainText(
            self._t("etp12.subscription_active", channels=len(value.channel_ids))
        )
        self._refresh_acquisition_controls()

    def _on_channel_batch(self, batch: Etp12ChannelBatch) -> None:
        self.discovery.observe(batch)
        runtime = self.acquisition_runtime
        if runtime is not None and runtime.state is Etp12AcquisitionState.OPEN:
            try:
                runtime.submit_channel_batch(batch)
                if runtime.controller.pending_count >= runtime.config.drain_batch_size:
                    runtime.drain(limit=runtime.config.drain_batch_size)
                    self._notify_dataset_changed(runtime)
            except Exception as exc:  # noqa: BLE001
                self.details.appendPlainText(str(exc))
        for point in batch.points:
            self._latest_channel_values[point.channel_id] = (point.index, point.value)
        by_id: dict[int, int] = {}
        for table_row in range(self.channel_table.rowCount()):
            item = self.channel_table.item(table_row, 0)
            if item is None:
                continue
            try:
                by_id[int(item.text())] = table_row
            except ValueError:
                continue
        for channel_id, (index, value) in self._latest_channel_values.items():
            row = by_id.get(channel_id)
            if row is None:
                row = self.channel_table.rowCount()
                self.channel_table.insertRow(row)
                self.channel_table.setItem(row, 0, QTableWidgetItem(str(channel_id)))
            self.channel_table.setItem(row, 3, QTableWidgetItem(str(index)))
            self.channel_table.setItem(row, 4, QTableWidgetItem(str(value)))
        self._refresh_acquisition_controls()

    def _restore_open_acquisition_session(self) -> None:
        if self.acquisition_runtime is not None:
            return
        well = self.well_provider() if self.well_provider is not None else None
        if well is None:
            return
        sessions = open_etp12_sessions(well)
        if not sessions:
            return
        snapshot = self.discovery.snapshot()
        if not snapshot.channels:
            return
        session = sessions[-1]
        try:
            commit = restore_etp12_import_review_commit(session, snapshot)
            runtime = Etp12AcquisitionRuntime(
                well,
                commit,
                session_id=session.session_id,
                metadata=self.channel_metadata_by_uri,
                session=session,
                config=Etp12AcquisitionConfig(
                    max_pending_records=256,
                    drain_batch_size=64,
                    checkpoint_every_records=500,
                    checkpoint_interval_seconds=60.0,
                    overlap_window_points=100_000,
                    backpressure_policy=Etp12BackpressurePolicy.DRAIN_THEN_RETRY,
                ),
            )
        except Exception as exc:  # noqa: BLE001
            self.details.appendPlainText(
                self._t("etp12.acquisition_restore_failed", error=str(exc))
            )
            return
        self.review_commit = commit
        self.acquisition_runtime = runtime
        self._notify_dataset_changed(runtime)
        self.details.appendPlainText(
            self._t(
                "etp12.acquisition_restored",
                session=session.session_id,
                sequence=session.last_sequence,
            )
        )
        self._refresh_acquisition_controls()

    def _review_import(self) -> None:
        snapshot = self.discovery.snapshot()
        if not snapshot.channels:
            QMessageBox.warning(self, self._t("etp12.title"), self._t("etp12.review_no_channels"))
            return
        dialog = Etp12ImportReviewDialog(
            snapshot, self, language=self.localizer.language
        )
        if dialog.exec() != QDialog.DialogCode.Accepted or dialog.commit_result is None:
            return
        self.review_commit = dialog.commit_result
        self.details.appendPlainText(
            self._t(
                "etp12.review_committed",
                channels=len(dialog.commit_result.schema.curves),
                digest=dialog.commit_result.schema_digest[:16],
            )
        )
        self._refresh_acquisition_controls()

    def _start_acquisition(self) -> None:
        commit = self.review_commit
        well = self.well_provider() if self.well_provider is not None else None
        snapshot = self.discovery.snapshot()
        if commit is None or commit.review.discovery_fingerprint != snapshot.fingerprint:
            QMessageBox.warning(self, self._t("etp12.title"), self._t("etp12.review_required"))
            return
        if well is None:
            QMessageBox.warning(self, self._t("etp12.title"), self._t("etp12.well_required"))
            return
        try:
            runtime = Etp12AcquisitionRuntime(
                well,
                commit,
                session_id=f"etp12-{uuid4()}",
                metadata=self.channel_metadata_by_uri,
                config=Etp12AcquisitionConfig(
                    max_pending_records=256,
                    drain_batch_size=64,
                    checkpoint_every_records=500,
                    checkpoint_interval_seconds=60.0,
                    overlap_window_points=100_000,
                    backpressure_policy=Etp12BackpressurePolicy.DRAIN_THEN_RETRY,
                ),
            )
        except Exception as exc:  # noqa: BLE001
            QMessageBox.critical(self, self._t("etp12.title"), str(exc))
            return
        self.acquisition_runtime = runtime
        self._notify_dataset_changed(runtime)
        self.details.appendPlainText(
            self._t("etp12.acquisition_started", session=runtime.session.session_id)
        )
        self._refresh_acquisition_controls()

    def _flush_acquisition(self) -> None:
        runtime = self.acquisition_runtime
        if runtime is None or runtime.state is not Etp12AcquisitionState.OPEN:
            return
        try:
            applied = runtime.flush()
        except Exception as exc:  # noqa: BLE001
            QMessageBox.critical(self, self._t("etp12.title"), str(exc))
            return
        if applied:
            self._notify_dataset_changed(runtime)
        self.details.appendPlainText(self._t("etp12.acquisition_flushed", count=len(applied)))
        self._refresh_acquisition_controls()

    def _close_acquisition(self) -> None:
        runtime = self.acquisition_runtime
        if runtime is None or runtime.state is not Etp12AcquisitionState.OPEN:
            return
        try:
            checkpoint = runtime.close()
        except Exception as exc:  # noqa: BLE001
            QMessageBox.critical(self, self._t("etp12.title"), str(exc))
            return
        self._notify_dataset_changed(runtime)
        self.details.appendPlainText(
            self._t("etp12.acquisition_closed", sequence=checkpoint.sequence)
        )
        self._refresh_acquisition_controls()

    def _notify_dataset_changed(self, runtime: Etp12AcquisitionRuntime) -> None:
        callback = self.on_dataset_changed
        if callback is not None:
            callback(runtime.session.dataset_schema.dataset_id)

    def _refresh_acquisition_controls(self) -> None:
        snapshot = self.discovery.snapshot()
        runtime = self.acquisition_runtime
        open_runtime = runtime is not None and runtime.state is Etp12AcquisitionState.OPEN
        commit_current = (
            self.review_commit is not None
            and self.review_commit.review.discovery_fingerprint == snapshot.fingerprint
        )
        has_well = self.well_provider is not None and self.well_provider() is not None
        self.review_button.setEnabled(bool(snapshot.channels) and not open_runtime)
        self.start_acquisition_button.setEnabled(
            commit_current and runtime is None and has_well
        )
        self.flush_acquisition_button.setEnabled(
            open_runtime and runtime is not None and runtime.controller.pending_count > 0
        )
        self.close_acquisition_button.setEnabled(open_runtime)

    def _on_snapshot(self, value: object) -> None:
        if not isinstance(value, Etp12SessionSnapshot):
            self._reject_worker_payload("session-snapshot", value)
            return
        self.details.appendPlainText(
            self._t(
                "etp12.snapshot",
                state=value.state.value,
                sent=value.sent_messages,
                received=value.received_messages,
                ack=value.acknowledgements_sent,
                pending=value.pending_requests,
                subscriptions=len(value.subscriptions),
            )
        )
        if value.state.value in {"closed", "failed", "disconnected"}:
            self._connected = False
            self._set_connected_controls(False)

    def _on_failed(self, message: str) -> None:
        self.status.setText(message)
        QMessageBox.critical(self, self._t("etp12.title"), message)

    def _tree_selection(self, current: QTreeWidgetItem | None, _previous: QTreeWidgetItem | None) -> None:
        self.get_object_button.setEnabled(
            self._connected
            and current is not None
            and isinstance(current.data(0, Qt.ItemDataRole.UserRole), Etp12Resource)
        )

    def _set_connected_controls(self, connected: bool) -> None:
        self.reconnect_button.setEnabled(connected)
        self.disconnect_button.setEnabled(connected)
        self.discover_button.setEnabled(connected)
        self.array_button.setEnabled(connected)
        self.metadata_button.setEnabled(connected)
        self.subscribe_button.setEnabled(connected)
        self.unsubscribe_button.setEnabled(connected)
        self._tree_selection(self.tree.currentItem(), None)

    def closeEvent(self, event) -> None:  # noqa: N802 - Qt API
        runtime = self.acquisition_runtime
        if runtime is not None and runtime.state is Etp12AcquisitionState.OPEN:
            try:
                runtime.close()
                self._notify_dataset_changed(runtime)
            except Exception as exc:  # noqa: BLE001
                self.details.appendPlainText(str(exc))
        self.worker.submit("stop")
        self.worker.wait(5000)
        super().closeEvent(event)
