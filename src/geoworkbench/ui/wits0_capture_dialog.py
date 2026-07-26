from __future__ import annotations

from pathlib import Path

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
    Wits0ParsedFrame,
    load_builtin_wits0_profile,
)
from geoworkbench.services.localization import AppLanguage, Localizer


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
    ) -> None:
        super().__init__(parent)
        self.localizer = Localizer.create(language)
        self.settings = QSettings()
        self.engine: Wits0CaptureEngine | None = None
        self.profile = load_builtin_wits0_profile()

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
        self.tabs.addTab(self.raw_text, self._t("wits0.raw_tab"))
        self.tabs.addTab(self.parsed_text, self._t("wits0.parsed_tab"))
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
        actions.addStretch(1)
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Close, self)
        buttons.rejected.connect(self.close)
        actions.addWidget(buttons)
        root.addLayout(actions)

        self.poll_timer = QTimer(self)
        self.poll_timer.setInterval(100)
        self.poll_timer.timeout.connect(self._poll_engine)
        self.poll_timer.start()
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
        self.errors_value = QLabel("0", group)
        self.last_received_value = QLabel("—", group)

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
            ("wits0.errors", self.errors_value),
            ("wits0.last_received", self.last_received_value),
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
        engine = Wits0CaptureEngine(config, profile=self.profile)
        try:
            engine.start()
        except RuntimeError as exc:
            QMessageBox.critical(self, self._t("wits0.title"), str(exc))
            return
        self.engine = engine
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
        return Wits0CaptureConfig(
            mode=mode,
            host=self.host_edit.text().strip(),
            port=self.port_spin.value(),
            raw_directory=Path(self.raw_directory_edit.text()).expanduser(),
            source_name=self.source_edit.text().strip(),
            encoding=self.profile.encoding,
        )

    def _save_settings(self, config: Wits0CaptureConfig) -> None:
        self.settings.setValue("wits0/mode", config.mode.value)
        self.settings.setValue("wits0/host", config.host)
        self.settings.setValue("wits0/port", config.port)
        self.settings.setValue("wits0/source_name", config.source_name)
        self.settings.setValue("wits0/raw_directory", str(config.raw_directory))
        self.settings.sync()

    def _poll_engine(self) -> None:
        engine = self.engine
        if engine is None:
            self._refresh_snapshot()
            return
        for event in engine.drain_events(max_events=500):
            if event.kind is Wits0CaptureEventKind.FRAME and event.frame is not None:
                text = event.frame.decode(engine.config.encoding, errors="replace")
                self.raw_text.appendPlainText(text)
                if event.parsed_frame is not None:
                    self.parsed_text.appendPlainText(
                        self._format_parsed_frame(event.parsed_frame)
                    )
                continue
            detail = event.message
            if event.peer:
                detail = f"{detail} [{event.peer}]"
            if event.raw_file:
                detail = f"{detail}: {event.raw_file}"
            self.event_text.appendPlainText(f"{event.occurred_at}  {detail}")
        self._refresh_snapshot()
        self._refresh_controls()

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
        self.state_value.setText(self._t(f"wits0.state_{state.value}"))

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
        ):
            widget.setEnabled(not running)
        self.start_button.setEnabled(not running)
        self.stop_button.setEnabled(running)

    def closeEvent(self, event) -> None:  # type: ignore[no-untyped-def]
        engine = self.engine
        if engine is not None and engine.is_running:
            engine.stop(timeout=2.0)
        self.poll_timer.stop()
        super().closeEvent(event)

    def _t(self, key: str, **values: object) -> str:
        return self.localizer.text(key, **values)
