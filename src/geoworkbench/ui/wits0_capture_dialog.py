from __future__ import annotations

from pathlib import Path
from typing import Callable, TYPE_CHECKING
from uuid import uuid4

from PySide6.QtCore import QSettings, QStandardPaths, QTimer
from PySide6.QtWidgets import (
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFileDialog,
    QFormLayout,
    QGridLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPlainTextEdit,
    QPushButton,
    QSpinBox,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

from geoworkbench.acquisition import (
    Wits0CaptureConfig,
    Wits0CaptureEngine,
    Wits0CaptureEventKind,
    Wits0CaptureState,
    Wits0ConnectionMode,
    Wits0DiskSpacePolicy,
    Wits0RawRetentionPolicy,
    Wits0WorkspaceSettings,
    Wits0ParsedFrame,
    load_builtin_wits0_profile,
)
from geoworkbench.services.localization import AppLanguage, Localizer
from geoworkbench.services.wits0_acquisition import (
    Wits0AcquisitionBackpressureError,
    Wits0AcquisitionConfig,
    Wits0AcquisitionRuntime,
    Wits0AcquisitionState,
    Wits0BackpressurePolicy,
)
from geoworkbench.services.wits0_recovery import (
    open_wits0_sessions,
    restore_wits0_import_review_commit,
)
from geoworkbench.services.wits0_import_review import (
    Wits0CustomProfile,
    Wits0DiscoveryAccumulator,
    Wits0ImportReviewCommit,
    load_wits0_custom_profile,
    save_wits0_custom_profile,
)
from geoworkbench.ui.wits0_import_review_dialog import Wits0ImportReviewDialog
from geoworkbench.ui.wits0_live_view import Wits0LiveViewWidget

if TYPE_CHECKING:
    from geoworkbench.domain.models import Well


class Wits0CaptureDialog(QDialog):
    """Modeless WITS0 TCP raw-capture monitor.

    Socket I/O remains in :class:`Wits0CaptureEngine`; this dialog only polls immutable events
    through a timer and therefore never blocks the Qt GUI thread on ``accept`` or ``recv``.
    """

    def __init__(
        self,
        parent: QWidget | None = None,
        *,
        language: AppLanguage = AppLanguage.RU,
        well_provider: Callable[[], "Well | None"] | None = None,
        on_dataset_changed: Callable[[str], None] | None = None,
    ) -> None:
        super().__init__(parent)
        self.language = language
        self.localizer = Localizer.create(language)
        self.settings = QSettings()
        self.workspace_settings = Wits0WorkspaceSettings(self.settings)
        self._last_workspace_state = None
        self._connection_events_recorded: set[tuple[str, bool]] = set()
        self.well_provider = well_provider
        self.on_dataset_changed = on_dataset_changed
        self.engine: Wits0CaptureEngine | None = None
        self.acquisition_runtime: Wits0AcquisitionRuntime | None = None
        self.profile = load_builtin_wits0_profile()
        self.discovery = Wits0DiscoveryAccumulator(self.profile)
        self.review_commit: Wits0ImportReviewCommit | None = None
        self.review_profile_path: Path | None = None
        self.previous_custom_profile = self._load_previous_custom_profile()

        self.setWindowTitle(self._t("wits0.title"))
        self.resize(980, 720)
        root = QVBoxLayout(self)
        root.addWidget(self._build_connection_group())
        root.addWidget(self._build_status_group())

        self.tabs = QTabWidget(self)
        self.raw_text = QPlainTextEdit(self)
        self.raw_text.setReadOnly(True)
        self.raw_text.document().setMaximumBlockCount(4_000)
        self.parsed_text = QPlainTextEdit(self)
        self.parsed_text.setReadOnly(True)
        self.parsed_text.document().setMaximumBlockCount(8_000)
        self.event_text = QPlainTextEdit(self)
        self.event_text.setReadOnly(True)
        self.event_text.document().setMaximumBlockCount(4_000)
        self.live_view = Wits0LiveViewWidget(self, language=language)
        self.tabs.addTab(self.raw_text, self._t("wits0.raw_tab"))
        self.tabs.addTab(self.parsed_text, self._t("wits0.parsed_tab"))
        self.tabs.addTab(self.live_view, self._t("wits0.live_tab"))
        self.tabs.addTab(self.event_text, self._t("wits0.events_tab"))
        root.addWidget(self.tabs, 1)

        actions = QHBoxLayout()
        self.start_button = QPushButton(self._t("wits0.start"), self)
        self.stop_button = QPushButton(self._t("wits0.stop"), self)
        self.stop_button.setEnabled(False)
        self.start_button.clicked.connect(self._start_capture)
        self.stop_button.clicked.connect(self._stop_capture)
        actions.addWidget(self.start_button)
        actions.addWidget(self.stop_button)
        self.review_button = QPushButton(self._t("wits0.review_action"), self)
        self.review_button.clicked.connect(self._open_import_review)
        self.reset_discovery_button = QPushButton(
            self._t("wits0.reset_discovery_action"),
            self,
        )
        self.reset_discovery_button.clicked.connect(self._reset_discovery)
        actions.addWidget(self.review_button)
        actions.addWidget(self.reset_discovery_button)
        self.start_acquisition_button = QPushButton(
            self._t("wits0.acquisition_start"), self
        )
        self.flush_acquisition_button = QPushButton(
            self._t("wits0.acquisition_flush"), self
        )
        self.close_acquisition_button = QPushButton(
            self._t("wits0.acquisition_close"), self
        )
        self.start_acquisition_button.clicked.connect(self._start_acquisition)
        self.flush_acquisition_button.clicked.connect(self._flush_acquisition)
        self.close_acquisition_button.clicked.connect(self._close_acquisition)
        actions.addWidget(self.start_acquisition_button)
        actions.addWidget(self.flush_acquisition_button)
        actions.addWidget(self.close_acquisition_button)
        actions.addStretch(1)
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Close, self)
        buttons.rejected.connect(self.close)
        actions.addWidget(buttons)
        root.addLayout(actions)

        self.poll_timer = QTimer(self)
        self.poll_timer.setInterval(100)
        self.poll_timer.timeout.connect(self._poll_engine)
        self.poll_timer.start()
        self._restore_open_acquisition_session()
        self._refresh_controls()
        self._refresh_snapshot()

    def _build_connection_group(self) -> QGroupBox:
        group = QGroupBox(self._t("wits0.connection_group"), self)
        form = QFormLayout(group)

        self.mode_combo = QComboBox(group)
        self.mode_combo.addItem(
            self._t("wits0.mode_server"), Wits0ConnectionMode.TCP_SERVER.value
        )
        self.mode_combo.addItem(
            self._t("wits0.mode_client"), Wits0ConnectionMode.TCP_CLIENT.value
        )
        saved_mode = str(
            self.settings.value("wits0/mode", Wits0ConnectionMode.TCP_SERVER.value)
        )
        mode_index = self.mode_combo.findData(saved_mode)
        self.mode_combo.setCurrentIndex(max(0, mode_index))
        form.addRow(self._t("wits0.mode"), self.mode_combo)

        self.host_edit = QLineEdit(str(self.settings.value("wits0/host", "0.0.0.0")), group)
        form.addRow(self._t("wits0.host"), self.host_edit)

        self.port_spin = QSpinBox(group)
        self.port_spin.setRange(1, 65_535)
        self.port_spin.setValue(int(self.settings.value("wits0/port", 2041)))
        form.addRow(self._t("wits0.port"), self.port_spin)

        self.disk_critical_spin = QSpinBox(group)
        self.disk_critical_spin.setRange(64, 1_048_576)
        self.disk_critical_spin.setSuffix(" MB")
        self.disk_critical_spin.setValue(
            int(self.settings.value("wits0/disk_critical_mb", 512))
        )
        form.addRow(self._t("wits0.disk_critical_mb"), self.disk_critical_spin)

        self.disk_warning_spin = QSpinBox(group)
        self.disk_warning_spin.setRange(64, 1_048_576)
        self.disk_warning_spin.setSuffix(" MB")
        self.disk_warning_spin.setValue(
            int(self.settings.value("wits0/disk_warning_mb", 2048))
        )
        form.addRow(self._t("wits0.disk_warning_mb"), self.disk_warning_spin)

        self.retention_days_spin = QSpinBox(group)
        self.retention_days_spin.setRange(1, 3650)
        self.retention_days_spin.setValue(
            int(self.settings.value("wits0/retention_days", 30))
        )
        form.addRow(self._t("wits0.retention_days"), self.retention_days_spin)

        self.retention_gb_spin = QSpinBox(group)
        self.retention_gb_spin.setRange(1, 102_400)
        self.retention_gb_spin.setSuffix(" GB")
        self.retention_gb_spin.setValue(
            int(self.settings.value("wits0/retention_max_gb", 20))
        )
        form.addRow(self._t("wits0.retention_max_gb"), self.retention_gb_spin)

        self.retention_keep_spin = QSpinBox(group)
        self.retention_keep_spin.setRange(0, 10_000)
        self.retention_keep_spin.setValue(
            int(self.settings.value("wits0/retention_keep_segments", 4))
        )
        form.addRow(
            self._t("wits0.retention_keep_segments"),
            self.retention_keep_spin,
        )

        self.source_edit = QLineEdit(
            str(self.settings.value("wits0/source_name", "GeoScape-GSWITS")), group
        )
        form.addRow(self._t("wits0.source_name"), self.source_edit)

        default_raw = Path(
            QStandardPaths.writableLocation(
                QStandardPaths.StandardLocation.AppDataLocation
            )
        ) / "raw" / "wits0"
        raw_row = QWidget(group)
        raw_layout = QHBoxLayout(raw_row)
        raw_layout.setContentsMargins(0, 0, 0, 0)
        self.raw_directory_edit = QLineEdit(
            str(self.settings.value("wits0/raw_directory", str(default_raw))), raw_row
        )
        browse = QPushButton(self._t("wits0.browse"), raw_row)
        browse.clicked.connect(self._choose_raw_directory)
        raw_layout.addWidget(self.raw_directory_edit, 1)
        raw_layout.addWidget(browse)
        self.browse_button = browse
        form.addRow(self._t("wits0.raw_directory"), raw_row)

        profile_label = QLabel(
            self._t(
                "wits0.profile_value",
                title=self.profile.title,
                records=len(self.profile.records),
            ),
            group,
        )
        profile_label.setWordWrap(True)
        form.addRow(self._t("wits0.profile"), profile_label)

        warning = QLabel(self._t("wits0.capture_only_warning"), group)
        warning.setWordWrap(True)
        form.addRow("", warning)
        return group

    def _build_status_group(self) -> QGroupBox:
        group = QGroupBox(self._t("wits0.status_group"), self)
        layout = QGridLayout(group)
        self.state_value = QLabel("—", group)
        self.peer_value = QLabel("—", group)
        self.raw_file_value = QLabel("—", group)
        self.bytes_value = QLabel("0", group)
        self.frames_value = QLabel("0", group)
        self.parsed_fields_value = QLabel("0", group)
        self.parser_warnings_value = QLabel("0", group)
        self.parser_errors_value = QLabel("0", group)
        self.sequence_anomalies_value = QLabel("0", group)
        self.last_sequence_value = QLabel("—", group)
        self.discovered_channels_value = QLabel("0", group)
        self.review_state_value = QLabel("—", group)
        self.schema_digest_value = QLabel("—", group)
        self.custom_profile_value = QLabel("—", group)
        self.acquisition_state_value = QLabel("—", group)
        self.acquisition_pending_value = QLabel("0", group)
        self.acquisition_applied_value = QLabel("0", group)
        self.acquisition_skipped_value = QLabel("0", group)
        self.acquisition_checkpoints_value = QLabel("0", group)
        self.acquisition_backpressure_value = QLabel("0", group)
        self.errors_value = QLabel("0", group)
        self.last_received_value = QLabel("—", group)
        self.disk_state_value = QLabel("—", group)
        self.disk_free_value = QLabel("—", group)
        self.retention_deleted_value = QLabel("0 / 0 B", group)
        self.recovery_state_value = QLabel("—", group)

        rows = (
            ("wits0.state", self.state_value),
            ("wits0.peer", self.peer_value),
            ("wits0.raw_file", self.raw_file_value),
            ("wits0.bytes", self.bytes_value),
            ("wits0.frames", self.frames_value),
            ("wits0.parsed_fields", self.parsed_fields_value),
            ("wits0.parser_warnings", self.parser_warnings_value),
            ("wits0.parser_errors", self.parser_errors_value),
            ("wits0.sequence_anomalies", self.sequence_anomalies_value),
            ("wits0.last_sequence", self.last_sequence_value),
            ("wits0.discovered_channels", self.discovered_channels_value),
            ("wits0.review_state", self.review_state_value),
            ("wits0.schema_digest", self.schema_digest_value),
            ("wits0.custom_profile_file", self.custom_profile_value),
            ("wits0.acquisition_state", self.acquisition_state_value),
            ("wits0.acquisition_pending", self.acquisition_pending_value),
            ("wits0.acquisition_applied", self.acquisition_applied_value),
            ("wits0.acquisition_skipped", self.acquisition_skipped_value),
            ("wits0.acquisition_checkpoints", self.acquisition_checkpoints_value),
            ("wits0.acquisition_backpressure", self.acquisition_backpressure_value),
            ("wits0.errors", self.errors_value),
            ("wits0.last_received", self.last_received_value),
            ("wits0.disk_state", self.disk_state_value),
            ("wits0.disk_free", self.disk_free_value),
            ("wits0.retention_deleted", self.retention_deleted_value),
            ("wits0.recovery_state", self.recovery_state_value),
        )
        for row, (key, value) in enumerate(rows):
            layout.addWidget(QLabel(self._t(key), group), row, 0)
            layout.addWidget(value, row, 1)
        layout.setColumnStretch(1, 1)
        return group

    def _choose_raw_directory(self) -> None:
        selected = QFileDialog.getExistingDirectory(
            self,
            self._t("wits0.select_raw_directory"),
            self.raw_directory_edit.text(),
        )
        if selected:
            self.raw_directory_edit.setText(selected)

    def _start_capture(self) -> None:
        try:
            config = self._capture_config()
            config.raw_directory.mkdir(parents=True, exist_ok=True)
        except (OSError, ValueError) as exc:
            QMessageBox.critical(self, self._t("wits0.title"), str(exc))
            return
        self._save_settings(config)
        if self.review_commit is None and self.acquisition_runtime is None:
            self._reset_discovery(show_confirmation=False)
        engine = Wits0CaptureEngine(config, profile=self.profile)
        try:
            engine.start()
        except RuntimeError as exc:
            QMessageBox.critical(self, self._t("wits0.title"), str(exc))
            return
        self.engine = engine
        runtime = self.acquisition_runtime
        engine.set_recovery_context(
            acquisition_session_id=(
                runtime.session.session_id if runtime is not None else None
            ),
            custom_profile_path=(
                str(self.review_profile_path) if self.review_profile_path else None
            ),
        )
        self.event_text.appendPlainText(self._t("wits0.started_message"))
        self._refresh_controls()

    def _stop_capture(self) -> None:
        engine = self.engine
        if engine is None:
            return
        if not engine.stop(timeout=2.0):
            self.event_text.appendPlainText(self._t("wits0.stop_pending"))
        self._poll_engine()
        self._refresh_controls()

    def _capture_config(self) -> Wits0CaptureConfig:
        mode = Wits0ConnectionMode(str(self.mode_combo.currentData()))
        critical_mb = self.disk_critical_spin.value()
        warning_mb = max(critical_mb, self.disk_warning_spin.value())
        return Wits0CaptureConfig(
            mode=mode,
            host=self.host_edit.text().strip(),
            port=self.port_spin.value(),
            raw_directory=Path(self.raw_directory_edit.text()).expanduser(),
            source_name=self.source_edit.text().strip(),
            encoding=self.profile.encoding,
            disk_policy=Wits0DiskSpacePolicy(
                critical_free_bytes=critical_mb * 1024 * 1024,
                warning_free_bytes=warning_mb * 1024 * 1024,
            ),
            retention_policy=Wits0RawRetentionPolicy(
                max_age_days=self.retention_days_spin.value(),
                max_total_bytes=self.retention_gb_spin.value() * 1024**3,
                keep_min_segments=self.retention_keep_spin.value(),
            ),
        )

    def _save_settings(self, config: Wits0CaptureConfig) -> None:
        self.settings.setValue("wits0/mode", config.mode.value)
        self.settings.setValue("wits0/host", config.host)
        self.settings.setValue("wits0/port", config.port)
        self.settings.setValue("wits0/source_name", config.source_name)
        self.settings.setValue("wits0/raw_directory", str(config.raw_directory))
        self.settings.setValue(
            "wits0/disk_critical_mb",
            config.disk_policy.critical_free_bytes // (1024 * 1024),
        )
        self.settings.setValue(
            "wits0/disk_warning_mb",
            config.disk_policy.warning_free_bytes // (1024 * 1024),
        )
        self.settings.setValue(
            "wits0/retention_days",
            config.retention_policy.max_age_days or 30,
        )
        self.settings.setValue(
            "wits0/retention_max_gb",
            (config.retention_policy.max_total_bytes or 20 * 1024**3) // 1024**3,
        )
        self.settings.setValue(
            "wits0/retention_keep_segments",
            config.retention_policy.keep_min_segments,
        )
        self.settings.sync()

    def _poll_engine(self) -> None:
        engine = self.engine
        if engine is None:
            self._refresh_snapshot()
            self._persist_workspace_state()
            return
        for event in engine.drain_events(max_events=500):
            runtime = self.acquisition_runtime
            if (
                runtime is not None
                and runtime.state is Wits0AcquisitionState.OPEN
                and event.kind
                in {
                    Wits0CaptureEventKind.CONNECTION,
                    Wits0CaptureEventKind.DISCONNECTION,
                }
                and event.connection_id
            ):
                connected = event.kind is Wits0CaptureEventKind.CONNECTION
                event_key = (event.connection_id, connected)
                if event_key not in self._connection_events_recorded:
                    try:
                        runtime.submit_connection_event(
                            connected=connected,
                            occurred_at=event.occurred_at,
                            connection_id=event.connection_id,
                            peer=event.peer,
                            reason=event.reason,
                            raw_file=event.raw_file,
                            bytes_received=event.bytes_received,
                            frames_received=event.frames_received,
                        )
                    except Wits0AcquisitionBackpressureError as exc:
                        self.event_text.appendPlainText(
                            self._t(
                                "wits0.acquisition_backpressure_event",
                                error=str(exc),
                            )
                        )
                    else:
                        self._connection_events_recorded.add(event_key)
            if event.kind is Wits0CaptureEventKind.FRAME and event.frame is not None:
                text = event.frame.decode(engine.config.encoding, errors="replace")
                self.raw_text.appendPlainText(text)
                if event.parsed_frame is not None:
                    self.discovery.observe(event.parsed_frame)
                    self.parsed_text.appendPlainText(
                        self._format_parsed_frame(event.parsed_frame)
                    )
                    runtime = self.acquisition_runtime
                    if runtime is not None and runtime.state is Wits0AcquisitionState.OPEN:
                        try:
                            runtime.submit_frame(event.parsed_frame)
                        except Wits0AcquisitionBackpressureError as exc:
                            self.event_text.appendPlainText(
                                self._t("wits0.acquisition_backpressure_event", error=str(exc))
                            )
                continue
            detail = event.message
            if event.peer:
                detail = f"{detail} [{event.peer}]"
            if event.raw_file:
                detail = f"{detail}: {event.raw_file}"
            self.event_text.appendPlainText(f"{event.occurred_at}  {detail}")
        runtime = self.acquisition_runtime
        if runtime is not None and runtime.state is Wits0AcquisitionState.OPEN:
            try:
                applied = runtime.drain(limit=runtime.config.drain_batch_size)
            except Exception as exc:
                self.event_text.appendPlainText(
                    self._t("wits0.acquisition_error_event", error=str(exc))
                )
            else:
                if applied:
                    self._notify_dataset_changed(runtime)
        self._refresh_snapshot()
        self._refresh_controls()
        self._persist_workspace_state()

    def _refresh_snapshot(self) -> None:
        snapshot = self.engine.snapshot() if self.engine is not None else None
        if snapshot is None:
            state = Wits0CaptureState.STOPPED
            self.peer_value.setText("—")
            self.raw_file_value.setText("—")
            self.bytes_value.setText("0")
            self.frames_value.setText("0")
            self.parsed_fields_value.setText("0")
            self.parser_warnings_value.setText("0")
            self.parser_errors_value.setText("0")
            self.sequence_anomalies_value.setText("0")
            self.last_sequence_value.setText("—")
            self.errors_value.setText("0")
            self.last_received_value.setText("—")
            self.disk_state_value.setText("—")
            self.disk_free_value.setText("—")
            self.retention_deleted_value.setText("0 / 0 B")
            self.recovery_state_value.setText("—")
        else:
            state = snapshot.state
            self.peer_value.setText(snapshot.current_peer or "—")
            self.raw_file_value.setText(snapshot.current_raw_file or "—")
            self.raw_file_value.setToolTip(snapshot.current_raw_file or "")
            self.bytes_value.setText(f"{snapshot.bytes_received:,}".replace(",", " "))
            self.frames_value.setText(str(snapshot.frames_received))
            self.parsed_fields_value.setText(str(snapshot.parsed_fields))
            self.parser_warnings_value.setText(str(snapshot.parser_warnings))
            self.parser_errors_value.setText(str(snapshot.parser_errors))
            sequence_anomalies = (
                snapshot.sequence_gaps
                + snapshot.sequence_duplicates
                + snapshot.sequence_out_of_order
            )
            self.sequence_anomalies_value.setText(str(sequence_anomalies))
            self.last_sequence_value.setText(snapshot.last_sequence or "—")
            self.errors_value.setText(str(snapshot.errors))
            self.last_received_value.setText(snapshot.last_received_at or "—")
            self.disk_state_value.setText(
                self._t(f"wits0.disk_state_{snapshot.disk_state.value}")
            )
            self.disk_free_value.setText(self._format_bytes(snapshot.disk_free_bytes))
            self.retention_deleted_value.setText(
                f"{snapshot.retention_segments_deleted} / "
                f"{self._format_bytes(snapshot.retention_bytes_deleted)}"
            )
            recovery_key = (
                "wits0.recovery_unclean"
                if snapshot.recovery_unclean_detected
                else "wits0.recovery_clean"
            )
            self.recovery_state_value.setText(
                self._t(
                    recovery_key,
                    repaired=snapshot.recovery_sidecars_repaired,
                )
            )
        self.state_value.setText(self._t(f"wits0.state_{state.value}"))
        self._refresh_discovery_status()
        self._refresh_acquisition_status()

    def _format_parsed_frame(self, frame: Wits0ParsedFrame) -> str:
        record = f"{frame.record_no:02d}" if frame.record_no is not None else "—"
        sequence = str(frame.sequence_no) if frame.sequence_no is not None else "—"
        lines = [
            self._t(
                "wits0.parsed_frame_header",
                record=record,
                sequence=sequence,
                status=frame.sequence_status.value,
                fields=len(frame.fields),
            )
        ]
        for field in frame.fields:
            value = "—" if field.value is None else str(field.value)
            mnemonic = field.canonical_mnemonic or "UNKNOWN"
            unit = f" {field.source_unit}" if field.source_unit else ""
            marker = " !" if field.has_error else ""
            lines.append(
                f"{field.record_no:02d}{field.item_no:02d}  "
                f"{mnemonic:<28} = {value}{unit}{marker}"
            )
        if frame.diagnostics:
            lines.append(self._t("wits0.parsed_diagnostics"))
            lines.extend(
                f"  [{item.severity.value}] {item.code.value}: {item.message}"
                for item in frame.diagnostics
            )
        lines.append("")
        return "\n".join(lines)

    def _refresh_controls(self) -> None:
        running = self.engine is not None and self.engine.is_running
        for widget in (
            self.mode_combo,
            self.host_edit,
            self.port_spin,
            self.source_edit,
            self.raw_directory_edit,
            self.browse_button,
            self.disk_critical_spin,
            self.disk_warning_spin,
            self.retention_days_spin,
            self.retention_gb_spin,
            self.retention_keep_spin,
        ):
            widget.setEnabled(not running)
        self.start_button.setEnabled(not running)
        self.stop_button.setEnabled(running)
        has_channels = bool(self.discovery.snapshot().channels)
        runtime = self.acquisition_runtime
        acquisition_open = runtime is not None and runtime.state is Wits0AcquisitionState.OPEN
        commit_current = (
            self.review_commit is not None
            and (
                not has_channels
                or self.review_commit.custom_profile.discovery_fingerprint
                == self.discovery.snapshot().fingerprint
            )
        )
        self.review_button.setEnabled(has_channels and not acquisition_open)
        self.reset_discovery_button.setEnabled(
            not acquisition_open and (has_channels or self.review_commit is not None)
        )
        has_well = self.well_provider is not None and self.well_provider() is not None
        self.start_acquisition_button.setEnabled(
            commit_current
            and self.acquisition_runtime is None
            and not acquisition_open
            and has_well
        )
        self.flush_acquisition_button.setEnabled(
            acquisition_open and runtime is not None and runtime.controller.pending_count > 0
        )
        self.close_acquisition_button.setEnabled(acquisition_open)


    def _start_acquisition(self) -> None:
        commit = self.review_commit
        well = self.well_provider() if self.well_provider is not None else None
        snapshot = self.discovery.snapshot()
        if commit is None or commit.custom_profile.discovery_fingerprint != snapshot.fingerprint:
            QMessageBox.warning(
                self,
                self._t("wits0.title"),
                self._t("wits0.acquisition_review_required"),
            )
            return
        if well is None:
            QMessageBox.warning(
                self,
                self._t("wits0.title"),
                self._t("wits0.acquisition_well_required"),
            )
            return
        try:
            runtime = Wits0AcquisitionRuntime(
                well,
                commit,
                session_id=f"wits0-{uuid4()}",
                config=Wits0AcquisitionConfig(
                    max_pending_records=256,
                    drain_batch_size=64,
                    checkpoint_every_records=500,
                    checkpoint_interval_seconds=60.0,
                    backpressure_policy=Wits0BackpressurePolicy.DRAIN_THEN_RETRY,
                ),
            )
        except (ValueError, RuntimeError) as exc:
            QMessageBox.critical(self, self._t("wits0.title"), str(exc))
            return
        self.acquisition_runtime = runtime
        engine = self.engine
        if engine is not None:
            engine.set_recovery_context(
                acquisition_session_id=runtime.session.session_id,
                custom_profile_path=(
                    str(self.review_profile_path) if self.review_profile_path else None
                ),
            )
        self._notify_dataset_changed(runtime)
        self._restore_workspace_state(runtime)
        snapshot = engine.snapshot() if engine is not None else None
        if (
            snapshot is not None
            and snapshot.state is Wits0CaptureState.CONNECTED
            and snapshot.current_connection_id
        ):
            try:
                runtime.submit_connection_event(
                    connected=True,
                    occurred_at=snapshot.last_received_at or snapshot.started_at or _utc_now(),
                    connection_id=snapshot.current_connection_id,
                    peer=snapshot.current_peer,
                    raw_file=snapshot.current_raw_file,
                    reason="session_started_while_connected",
                )
            except Wits0AcquisitionBackpressureError as exc:
                self.event_text.appendPlainText(
                    self._t("wits0.acquisition_backpressure_event", error=str(exc))
                )
            else:
                self._connection_events_recorded.add(
                    (snapshot.current_connection_id, True)
                )
        self.event_text.appendPlainText(
            self._t(
                "wits0.acquisition_started_event",
                session=runtime.session.session_id,
                dataset=runtime.session.dataset_schema.name,
            )
        )
        self._refresh_acquisition_status()
        self._refresh_controls()

    def _flush_acquisition(self) -> None:
        runtime = self.acquisition_runtime
        if runtime is None or runtime.state is not Wits0AcquisitionState.OPEN:
            return
        try:
            applied = runtime.flush()
        except Exception as exc:
            QMessageBox.critical(self, self._t("wits0.title"), str(exc))
            return
        if applied:
            self._notify_dataset_changed(runtime)
        self._persist_workspace_state()
        self.event_text.appendPlainText(
            self._t("wits0.acquisition_flushed_event", count=len(applied))
        )
        self._refresh_acquisition_status()
        self._refresh_controls()

    def _close_acquisition(self) -> None:
        runtime = self.acquisition_runtime
        if runtime is None or runtime.state is not Wits0AcquisitionState.OPEN:
            return
        engine = self.engine
        if engine is not None and engine.is_running:
            engine.stop(timeout=2.0)
            self._poll_engine()
        try:
            checkpoint = runtime.close()
        except Exception as exc:
            QMessageBox.critical(self, self._t("wits0.title"), str(exc))
            return
        self._notify_dataset_changed(runtime)
        self._persist_workspace_state()
        if engine is not None:
            engine.set_recovery_context(
                acquisition_session_id=None,
                custom_profile_path=(
                    str(self.review_profile_path) if self.review_profile_path else None
                ),
            )
        self.event_text.appendPlainText(
            self._t(
                "wits0.acquisition_closed_event",
                sequence=checkpoint.sequence,
                checkpoint=checkpoint.checkpoint_id,
            )
        )
        self._refresh_acquisition_status()
        self._refresh_controls()

    def _notify_dataset_changed(self, runtime: Wits0AcquisitionRuntime) -> None:
        self.live_view.bind_runtime(runtime)
        callback = self.on_dataset_changed
        if callback is not None:
            callback(runtime.session.dataset_schema.dataset_id)

    def _refresh_acquisition_status(self) -> None:
        runtime = self.acquisition_runtime
        if runtime is None:
            self.acquisition_state_value.setText(self._t("wits0.acquisition_state_none"))
            self.acquisition_pending_value.setText("0")
            self.acquisition_applied_value.setText("0")
            self.acquisition_skipped_value.setText("0")
            self.acquisition_checkpoints_value.setText("0")
            self.acquisition_backpressure_value.setText("0")
            return
        snapshot = runtime.snapshot()
        self.acquisition_state_value.setText(
            self._t(f"wits0.acquisition_state_{snapshot.state.value}")
        )
        self.acquisition_pending_value.setText(str(snapshot.pending_records))
        self.acquisition_applied_value.setText(str(snapshot.records_applied))
        self.acquisition_skipped_value.setText(str(snapshot.frames_skipped))
        self.acquisition_checkpoints_value.setText(str(snapshot.checkpoints_created))
        self.acquisition_backpressure_value.setText(str(snapshot.backpressure_count))

    def _custom_profile_directory(self) -> Path:
        return Path(
            QStandardPaths.writableLocation(
                QStandardPaths.StandardLocation.AppDataLocation
            )
        ) / "wits0" / "profiles"

    def _load_previous_custom_profile(self) -> Wits0CustomProfile | None:
        raw_path = str(self.settings.value("wits0/custom_profile_path", "")).strip()
        if not raw_path:
            return None
        try:
            profile = load_wits0_custom_profile(raw_path)
        except ValueError:
            return None
        if (
            profile.base_profile_id != self.profile.profile_id
            or profile.base_profile_version != self.profile.version
        ):
            return None
        self.review_profile_path = Path(raw_path)
        return profile

    def _open_import_review(self) -> None:
        snapshot = self.discovery.snapshot()
        if not snapshot.channels:
            QMessageBox.information(
                self,
                self._t("wits0_review.title"),
                self._t("wits0.review_no_channels"),
            )
            return
        profile_directory = self._custom_profile_directory()
        dialog = Wits0ImportReviewDialog(
            snapshot,
            self.profile,
            self,
            language=self.language,
            custom_profile=self.previous_custom_profile,
            dataset_name=self.source_edit.text().strip() or "WITS0 Live",
            profile_directory=profile_directory,
        )
        if dialog.exec() != QDialog.DialogCode.Accepted or dialog.commit_result is None:
            return
        commit = dialog.commit_result
        try:
            profile_path = save_wits0_custom_profile(
                commit.custom_profile,
                profile_directory,
            )
        except (OSError, ValueError) as exc:
            QMessageBox.critical(self, self._t("wits0_review.title"), str(exc))
            return
        self.review_commit = commit
        self.previous_custom_profile = commit.custom_profile
        self.review_profile_path = profile_path
        self.settings.setValue("wits0/custom_profile_path", str(profile_path))
        self.settings.sync()
        self._refresh_discovery_status()
        self._refresh_controls()
        QMessageBox.information(
            self,
            self._t("wits0_review.title"),
            self._t(
                "wits0.review_saved",
                digest=commit.schema_digest,
                path=str(profile_path),
            ),
        )

    def _reset_discovery(
        self,
        _checked: bool = False,
        *,
        show_confirmation: bool = True,
    ) -> None:
        snapshot = self.discovery.snapshot()
        runtime = self.acquisition_runtime
        if runtime is not None and runtime.state is Wits0AcquisitionState.OPEN:
            QMessageBox.warning(
                self,
                self._t("wits0_review.title"),
                self._t("wits0.acquisition_close_before_reset"),
            )
            return
        if show_confirmation and (snapshot.channels or self.review_commit is not None):
            answer = QMessageBox.question(
                self,
                self._t("wits0_review.title"),
                self._t("wits0.reset_discovery_confirm"),
            )
            if answer is not QMessageBox.StandardButton.Yes:
                return
        self.discovery.reset()
        self.review_commit = None
        self.review_profile_path = None
        self._refresh_discovery_status()
        self._refresh_controls()

    def _refresh_discovery_status(self) -> None:
        snapshot = self.discovery.snapshot()
        commit = self.review_commit
        channel_count = len(snapshot.channels)
        if channel_count == 0 and commit is not None:
            channel_count = sum(
                1 for item in commit.custom_profile.channels if item.import_enabled
            )
        self.discovered_channels_value.setText(str(channel_count))
        if not snapshot.channels and commit is not None:
            state_key = "wits0.review_state_recovered"
        elif not snapshot.channels:
            state_key = "wits0.review_state_empty"
        elif commit is None:
            state_key = "wits0.review_state_pending"
        elif commit.custom_profile.discovery_fingerprint == snapshot.fingerprint:
            state_key = "wits0.review_state_confirmed"
        else:
            state_key = "wits0.review_state_stale"
        self.review_state_value.setText(self._t(state_key))
        digest = commit.schema_digest if commit is not None else ""
        self.schema_digest_value.setText(digest[:16] if digest else "—")
        self.schema_digest_value.setToolTip(digest)
        profile_path = str(self.review_profile_path) if self.review_profile_path else ""
        self.custom_profile_value.setText(
            Path(profile_path).name if profile_path else "—"
        )
        self.custom_profile_value.setToolTip(profile_path)

    def _workspace_id(self, runtime: Wits0AcquisitionRuntime | None = None) -> str:
        active = runtime or self.acquisition_runtime
        if active is not None:
            return active.session.well_id
        well = self.well_provider() if self.well_provider is not None else None
        return well.well_id if well is not None else "default"

    def _persist_workspace_state(self) -> None:
        runtime = self.acquisition_runtime
        if runtime is None:
            return
        try:
            state = self.live_view.workspace_state()
        except (RuntimeError, ValueError):
            return
        if state == self._last_workspace_state:
            return
        self.workspace_settings.save(self._workspace_id(runtime), state)
        self._last_workspace_state = state

    def _restore_workspace_state(self, runtime: Wits0AcquisitionRuntime) -> None:
        state = self.workspace_settings.load(self._workspace_id(runtime))
        try:
            self.live_view.apply_workspace_state(state)
        except (RuntimeError, ValueError):
            return
        self._last_workspace_state = self.live_view.workspace_state()

    def _restore_open_acquisition_session(self) -> None:
        well = self.well_provider() if self.well_provider is not None else None
        custom_profile = self.previous_custom_profile
        if well is None or custom_profile is None:
            return
        sessions = open_wits0_sessions(well)
        if not sessions:
            return
        workspace = self.workspace_settings.load(well.well_id)
        session = next(
            (
                item
                for item in sessions
                if item.session_id == workspace.acquisition_session_id
            ),
            sessions[-1],
        )
        try:
            commit = restore_wits0_import_review_commit(session, custom_profile)
            runtime = Wits0AcquisitionRuntime(
                well,
                commit,
                session_id=session.session_id,
                session=session,
                config=Wits0AcquisitionConfig(
                    max_pending_records=256,
                    drain_batch_size=64,
                    checkpoint_every_records=500,
                    checkpoint_interval_seconds=60.0,
                    backpressure_policy=Wits0BackpressurePolicy.DRAIN_THEN_RETRY,
                ),
            )
        except (ValueError, RuntimeError) as exc:
            self.event_text.appendPlainText(
                self._t("wits0.recovery_restore_failed", error=str(exc))
            )
            return
        self.review_commit = commit
        self.acquisition_runtime = runtime
        self._notify_dataset_changed(runtime)
        self._restore_workspace_state(runtime)
        self.event_text.appendPlainText(
            self._t(
                "wits0.recovery_restored_event",
                session=session.session_id,
                sequence=session.last_sequence,
            )
        )

    @staticmethod
    def _format_bytes(value: int | None) -> str:
        if value is None:
            return "—"
        size = float(max(0, value))
        units = ("B", "KB", "MB", "GB", "TB")
        unit = units[0]
        for candidate in units:
            unit = candidate
            if size < 1024.0 or candidate == units[-1]:
                break
            size /= 1024.0
        precision = 0 if unit == "B" else 1
        return f"{size:.{precision}f} {unit}"

    def closeEvent(self, event) -> None:  # type: ignore[no-untyped-def]
        self._persist_workspace_state()
        engine = self.engine
        if engine is not None and engine.is_running:
            engine.stop(timeout=2.0)
            self._poll_engine()
        runtime = self.acquisition_runtime
        if runtime is not None and runtime.state is Wits0AcquisitionState.OPEN:
            try:
                runtime.close()
            except Exception as exc:
                self.event_text.appendPlainText(str(exc))
            else:
                self._notify_dataset_changed(runtime)
        self.poll_timer.stop()
        super().closeEvent(event)

    def _t(self, key: str, **values: object) -> str:
        return self.localizer.text(key, **values)


def _utc_now() -> str:
    from datetime import datetime, timezone

    return datetime.now(timezone.utc).isoformat(timespec="milliseconds").replace(
        "+00:00", "Z"
    )
