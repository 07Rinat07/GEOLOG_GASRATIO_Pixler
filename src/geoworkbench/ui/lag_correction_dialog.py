from __future__ import annotations

from datetime import datetime, timezone

import numpy as np
from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QAbstractItemView,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QDoubleSpinBox,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QMessageBox,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from geoworkbench.domain.lag_correction import (
    AnnularVolumeFlowLagParameters,
    ConstantTimeLagParameters,
    ControlPointLagParameters,
    LagCorrectionAxisMode,
    LagCorrectionMethod,
    LagCorrectionProfile,
    LagCorrectionTarget,
    LagDepthControlPoint,
    PumpStrokeLagParameters,
)
from geoworkbench.domain.models import Dataset, IndexRole, TimeDepthAggregationPolicy
from geoworkbench.project.lag_correction_controller import LagCorrectionProjectController
from geoworkbench.services.localization import AppLanguage


_TEXT = {
    AppLanguage.RU: {
        "title": "Версионная коррекция lag/depth",
        "profiles": "Профили",
        "new_profile": "Новый профиль",
        "name": "Имя профиля",
        "target": "Назначение",
        "time_index": "TIME индекс",
        "depth_index": "DEPTH индекс",
        "curves": "Корректируемые кривые",
        "method": "Метод",
        "aggregation": "Повторные TIME значения",
        "author": "Автор",
        "comment": "Комментарий ревизии",
        "constant": "Постоянная задержка",
        "volume_flow": "Объём затрубья / расход",
        "pump": "Насосные ходы",
        "points": "Контрольные точки",
        "lag_seconds": "Задержка, с",
        "annular_volume": "Объём затрубья, м³",
        "flow_rate": "Расход, м³/с",
        "pump_output": "Подача насоса, м³/ход",
        "strokes": "Ходы, 1/мин",
        "control_points": "Точки (строка:глубина; …)",
        "control_hint": "Номера строк вводятся с 1. Пример: 1:100; 20:118.5",
        "create": "Создать профиль",
        "add_revision": "Добавить ревизию",
        "activate": "Сделать активной",
        "delete": "Удалить профиль",
        "revision": "Ревизия",
        "preview": "Предпросмотр",
        "source_axis": "Показать исходную ось",
        "corrected_axis": "Показать скорректированную ось",
        "close": "Закрыть",
        "row": "Строка",
        "source_depth": "Исходная глубина",
        "corrected_depth": "Скорр. глубина",
        "delay": "Lag, с",
        "summary": "Строк: {rows}; валидных: {valid}; вне диапазона: {invalid}",
        "confirm_delete": "Удалить профиль и все его derived datasets?",
        "select_curve": "Выберите хотя бы одну кривую.",
        "select_indexes": "Выберите требуемые индексы.",
        "created": "Профиль создан: {name}",
        "revised": "Добавлена ревизия {revision}.",
        "activated": "Активирована ревизия {revision}.",
        "selected": "Открыта {mode} проекция, ревизия {revision}.",
        "mode_source": "исходная",
        "mode_corrected": "скорректированная",
        "target_gas": "Газ",
        "target_cuttings": "Шлам",
        "target_generic": "Другое",
    },
    AppLanguage.EN: {
        "title": "Versioned lag/depth correction",
        "profiles": "Profiles",
        "new_profile": "New profile",
        "name": "Profile name",
        "target": "Target",
        "time_index": "TIME index",
        "depth_index": "DEPTH index",
        "curves": "Target curves",
        "method": "Method",
        "aggregation": "Repeated TIME values",
        "author": "Author",
        "comment": "Revision comment",
        "constant": "Constant delay",
        "volume_flow": "Annular volume / flow",
        "pump": "Pump strokes",
        "points": "Control points",
        "lag_seconds": "Delay, s",
        "annular_volume": "Annular volume, m³",
        "flow_rate": "Flow rate, m³/s",
        "pump_output": "Pump output, m³/stroke",
        "strokes": "Strokes, 1/min",
        "control_points": "Points (row:depth; …)",
        "control_hint": "Rows are entered from 1. Example: 1:100; 20:118.5",
        "create": "Create profile",
        "add_revision": "Add revision",
        "activate": "Make active",
        "delete": "Delete profile",
        "revision": "Revision",
        "preview": "Preview",
        "source_axis": "Show source axis",
        "corrected_axis": "Show corrected axis",
        "close": "Close",
        "row": "Row",
        "source_depth": "Source depth",
        "corrected_depth": "Corrected depth",
        "delay": "Lag, s",
        "summary": "Rows: {rows}; valid: {valid}; outside range: {invalid}",
        "confirm_delete": "Delete the profile and all derived datasets?",
        "select_curve": "Select at least one curve.",
        "select_indexes": "Select the required indexes.",
        "created": "Profile created: {name}",
        "revised": "Revision {revision} added.",
        "activated": "Revision {revision} activated.",
        "selected": "Opened {mode} projection, revision {revision}.",
        "mode_source": "source",
        "mode_corrected": "corrected",
        "target_gas": "Gas",
        "target_cuttings": "Cuttings",
        "target_generic": "Generic",
    },
    AppLanguage.KK: {
        "title": "Нұсқаланатын lag/depth түзетуі",
        "profiles": "Профильдер",
        "new_profile": "Жаңа профиль",
        "name": "Профиль атауы",
        "target": "Мақсаты",
        "time_index": "TIME индексі",
        "depth_index": "DEPTH индексі",
        "curves": "Түзетілетін қисықтар",
        "method": "Әдіс",
        "aggregation": "Қайталанатын TIME мәндері",
        "author": "Автор",
        "comment": "Ревизия түсіндірмесі",
        "constant": "Тұрақты кідіріс",
        "volume_flow": "Сақиналы кеңістік көлемі / шығын",
        "pump": "Сорғы жүрістері",
        "points": "Бақылау нүктелері",
        "lag_seconds": "Кідіріс, с",
        "annular_volume": "Сақиналы көлем, м³",
        "flow_rate": "Шығын, м³/с",
        "pump_output": "Сорғы беруі, м³/жүріс",
        "strokes": "Жүрістер, 1/мин",
        "control_points": "Нүктелер (жол:тереңдік; …)",
        "control_hint": "Жол нөмірлері 1-ден енгізіледі. Мысал: 1:100; 20:118.5",
        "create": "Профиль жасау",
        "add_revision": "Ревизия қосу",
        "activate": "Белсенді ету",
        "delete": "Профильді жою",
        "revision": "Ревизия",
        "preview": "Алдын ала қарау",
        "source_axis": "Бастапқы осьті көрсету",
        "corrected_axis": "Түзетілген осьті көрсету",
        "close": "Жабу",
        "row": "Жол",
        "source_depth": "Бастапқы тереңдік",
        "corrected_depth": "Түзетілген тереңдік",
        "delay": "Lag, с",
        "summary": "Жолдар: {rows}; жарамды: {valid}; ауқымнан тыс: {invalid}",
        "confirm_delete": "Профиль мен оның барлық derived dataset-терін жою керек пе?",
        "select_curve": "Кемінде бір қисықты таңдаңыз.",
        "select_indexes": "Қажетті индекстерді таңдаңыз.",
        "created": "Профиль жасалды: {name}",
        "revised": "{revision} ревизиясы қосылды.",
        "activated": "{revision} ревизиясы белсендірілді.",
        "selected": "{mode} проекция ашылды, ревизия {revision}.",
        "mode_source": "бастапқы",
        "mode_corrected": "түзетілген",
        "target_gas": "Газ",
        "target_cuttings": "Шлам",
        "target_generic": "Басқа",
    },
}


class LagCorrectionDialog(QDialog):
    """Qt facade over the project-level immutable lag correction controller."""

    def __init__(
        self,
        source_dataset: Dataset,
        controller: LagCorrectionProjectController,
        parent: QWidget | None = None,
        *,
        language: AppLanguage = AppLanguage.RU,
    ) -> None:
        super().__init__(parent)
        self.source_dataset = source_dataset
        self.controller = controller
        self.text = _TEXT[language]
        self.setWindowTitle(self.text["title"])
        self.resize(920, 760)

        root = QVBoxLayout(self)
        form = QFormLayout()

        self.profile_selector = QComboBox()
        self.profile_selector.setObjectName("lag-correction-profile-selector")
        form.addRow(self.text["profiles"], self.profile_selector)

        self.name_edit = QLineEdit()
        self.name_edit.setObjectName("lag-correction-name")
        form.addRow(self.text["name"], self.name_edit)

        self.target_selector = QComboBox()
        self.target_selector.addItem(self.text["target_gas"], LagCorrectionTarget.GAS)
        self.target_selector.addItem(self.text["target_cuttings"], LagCorrectionTarget.CUTTINGS)
        self.target_selector.addItem(self.text["target_generic"], LagCorrectionTarget.GENERIC)
        form.addRow(self.text["target"], self.target_selector)

        self.time_selector = QComboBox()
        self.time_selector.addItem("—", None)
        self.depth_selector = QComboBox()
        for index in source_dataset.indexes.values():
            label = f"{index.mnemonic} [{index.unit or '—'}] · {index.index_id}"
            if index.role is IndexRole.TIME:
                self.time_selector.addItem(label, index.index_id)
            elif index.role is IndexRole.DEPTH:
                self.depth_selector.addItem(label, index.index_id)
        form.addRow(self.text["time_index"], self.time_selector)
        form.addRow(self.text["depth_index"], self.depth_selector)

        self.method_selector = QComboBox()
        self.method_selector.addItem(self.text["constant"], LagCorrectionMethod.CONSTANT_TIME)
        self.method_selector.addItem(
            self.text["volume_flow"], LagCorrectionMethod.ANNULAR_VOLUME_FLOW
        )
        self.method_selector.addItem(self.text["pump"], LagCorrectionMethod.PUMP_STROKES)
        self.method_selector.addItem(self.text["points"], LagCorrectionMethod.CONTROL_POINTS)
        form.addRow(self.text["method"], self.method_selector)

        self.policy_selector = QComboBox()
        for policy in TimeDepthAggregationPolicy:
            self.policy_selector.addItem(policy.value, policy)
        self.policy_selector.setCurrentIndex(
            self.policy_selector.findData(TimeDepthAggregationPolicy.MEAN)
        )
        form.addRow(self.text["aggregation"], self.policy_selector)

        self.author_edit = QLineEdit("operator")
        form.addRow(self.text["author"], self.author_edit)
        self.comment_edit = QLineEdit()
        form.addRow(self.text["comment"], self.comment_edit)
        root.addLayout(form)

        curves_group = QGroupBox(self.text["curves"])
        curves_layout = QVBoxLayout(curves_group)
        self.curve_list = QListWidget()
        self.curve_list.setObjectName("lag-correction-curves")
        self.curve_list.setSelectionMode(QAbstractItemView.SelectionMode.NoSelection)
        for curve_id, curve in source_dataset.curves.items():
            metadata = curve.metadata
            label = metadata.original_mnemonic
            if metadata.unit:
                label += f" [{metadata.unit}]"
            if metadata.description:
                label += f" — {metadata.description}"
            item = QListWidgetItem(label)
            item.setData(Qt.ItemDataRole.UserRole, curve_id)
            item.setFlags(item.flags() | Qt.ItemFlag.ItemIsUserCheckable)
            item.setCheckState(Qt.CheckState.Unchecked)
            self.curve_list.addItem(item)
        curves_layout.addWidget(self.curve_list)
        root.addWidget(curves_group)

        method_group = QGroupBox(self.text["method"])
        method_form = QFormLayout(method_group)
        self.lag_seconds_spin = self._positive_spin(maximum=86400.0, decimals=3)
        self.annular_volume_spin = self._positive_spin(maximum=100000.0, decimals=6)
        self.flow_rate_spin = self._positive_spin(maximum=1000.0, decimals=9)
        self.pump_output_spin = self._positive_spin(maximum=100.0, decimals=9)
        self.strokes_spin = self._positive_spin(maximum=10000.0, decimals=3)
        self.control_points_edit = QTextEdit()
        self.control_points_edit.setMaximumHeight(72)
        self.control_hint = QLabel(self.text["control_hint"])
        self.control_hint.setWordWrap(True)
        method_form.addRow(self.text["lag_seconds"], self.lag_seconds_spin)
        method_form.addRow(self.text["annular_volume"], self.annular_volume_spin)
        method_form.addRow(self.text["flow_rate"], self.flow_rate_spin)
        method_form.addRow(self.text["pump_output"], self.pump_output_spin)
        method_form.addRow(self.text["strokes"], self.strokes_spin)
        method_form.addRow(self.text["control_points"], self.control_points_edit)
        method_form.addRow("", self.control_hint)
        root.addWidget(method_group)

        revision_row = QHBoxLayout()
        self.revision_selector = QComboBox()
        self.revision_selector.setObjectName("lag-correction-revision-selector")
        self.save_button = QPushButton(self.text["create"])
        self.activate_button = QPushButton(self.text["activate"])
        self.delete_button = QPushButton(self.text["delete"])
        revision_row.addWidget(QLabel(self.text["revision"]))
        revision_row.addWidget(self.revision_selector)
        revision_row.addStretch(1)
        revision_row.addWidget(self.save_button)
        revision_row.addWidget(self.activate_button)
        revision_row.addWidget(self.delete_button)
        root.addLayout(revision_row)

        projection_row = QHBoxLayout()
        self.preview_button = QPushButton(self.text["preview"])
        self.source_axis_button = QPushButton(self.text["source_axis"])
        self.corrected_axis_button = QPushButton(self.text["corrected_axis"])
        projection_row.addWidget(self.preview_button)
        projection_row.addWidget(self.source_axis_button)
        projection_row.addWidget(self.corrected_axis_button)
        projection_row.addStretch(1)
        root.addLayout(projection_row)

        self.summary_label = QLabel()
        self.summary_label.setObjectName("lag-correction-preview-summary")
        root.addWidget(self.summary_label)
        self.preview_table = QTableWidget(0, 4)
        self.preview_table.setObjectName("lag-correction-preview")
        self.preview_table.setHorizontalHeaderLabels(
            [
                self.text["row"],
                self.text["source_depth"],
                self.text["corrected_depth"],
                self.text["delay"],
            ]
        )
        self.preview_table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.preview_table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.preview_table.verticalHeader().setVisible(False)
        root.addWidget(self.preview_table, 1)

        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Close)
        buttons.button(QDialogButtonBox.StandardButton.Close).setText(self.text["close"])
        buttons.rejected.connect(self.reject)
        root.addWidget(buttons)

        self.profile_selector.currentIndexChanged.connect(self._load_profile)
        self.revision_selector.currentIndexChanged.connect(self._load_revision)
        self.method_selector.currentIndexChanged.connect(self._update_method_controls)
        self.save_button.clicked.connect(self._save)
        self.activate_button.clicked.connect(self._activate)
        self.delete_button.clicked.connect(self._delete)
        self.preview_button.clicked.connect(self._preview)
        self.source_axis_button.clicked.connect(
            lambda: self._select_projection(LagCorrectionAxisMode.SOURCE)
        )
        self.corrected_axis_button.clicked.connect(
            lambda: self._select_projection(LagCorrectionAxisMode.CORRECTED)
        )
        self._refresh_profiles()
        self._update_method_controls()

    @staticmethod
    def _positive_spin(*, maximum: float, decimals: int) -> QDoubleSpinBox:
        spin = QDoubleSpinBox()
        spin.setDecimals(decimals)
        spin.setRange(0.0, maximum)
        spin.setSingleStep(1.0)
        return spin

    def _profiles(self) -> list[LagCorrectionProfile]:
        well = self.controller.session.current_well
        if well is None:
            return []
        return sorted(
            (
                profile
                for profile in well.lag_correction_profiles.values()
                if profile.source_dataset_id == self.source_dataset.dataset_id
            ),
            key=lambda profile: profile.name.casefold(),
        )

    def _refresh_profiles(self, selected_id: str | None = None) -> None:
        self.profile_selector.blockSignals(True)
        self.profile_selector.clear()
        self.profile_selector.addItem(self.text["new_profile"], None)
        for profile in self._profiles():
            self.profile_selector.addItem(profile.name, profile.profile_id)
        if selected_id is not None:
            index = self.profile_selector.findData(selected_id)
            self.profile_selector.setCurrentIndex(max(index, 0))
        self.profile_selector.blockSignals(False)
        self._load_profile()

    def _selected_profile(self) -> LagCorrectionProfile | None:
        profile_id = self.profile_selector.currentData()
        if profile_id is None:
            return None
        well = self.controller.session.current_well
        return None if well is None else well.lag_correction_profiles.get(str(profile_id))

    def _load_profile(self) -> None:
        profile = self._selected_profile()
        existing = profile is not None
        self.name_edit.setEnabled(not existing)
        self.target_selector.setEnabled(not existing)
        self.save_button.setText(self.text["add_revision"] if existing else self.text["create"])
        self.delete_button.setEnabled(existing)
        self.preview_button.setEnabled(existing)
        self.source_axis_button.setEnabled(existing)
        self.corrected_axis_button.setEnabled(existing)
        self.revision_selector.blockSignals(True)
        self.revision_selector.clear()
        if profile is None:
            self.name_edit.clear()
            self.revision_selector.setEnabled(False)
            self.activate_button.setEnabled(False)
            self.summary_label.clear()
            self.preview_table.setRowCount(0)
        else:
            self.name_edit.setText(profile.name)
            self.target_selector.setCurrentIndex(self.target_selector.findData(profile.target))
            for revision in profile.revisions:
                label = f"v{revision.revision}"
                if revision.revision == profile.active_revision:
                    label += " ✓"
                self.revision_selector.addItem(label, revision.revision)
            self.revision_selector.setCurrentIndex(
                self.revision_selector.findData(profile.active_revision)
            )
            self.revision_selector.setEnabled(True)
            self.activate_button.setEnabled(profile.latest_revision > 1)
        self.revision_selector.blockSignals(False)
        self._load_revision()

    def _load_revision(self) -> None:
        profile = self._selected_profile()
        if profile is None or self.revision_selector.currentData() is None:
            return
        revision = profile.revision_by_number(int(self.revision_selector.currentData()))
        self.time_selector.setCurrentIndex(
            self.time_selector.findData(revision.source_time_index_id)
        )
        self.depth_selector.setCurrentIndex(
            self.depth_selector.findData(revision.source_depth_index_id)
        )
        self.method_selector.setCurrentIndex(self.method_selector.findData(revision.method))
        self.policy_selector.setCurrentIndex(
            self.policy_selector.findData(revision.aggregation_policy)
        )
        self.comment_edit.setText(revision.comment)
        for index in range(self.curve_list.count()):
            item = self.curve_list.item(index)
            item.setCheckState(
                Qt.CheckState.Checked
                if str(item.data(Qt.ItemDataRole.UserRole)) in revision.target_curve_ids
                else Qt.CheckState.Unchecked
            )
        parameters = revision.parameters
        if isinstance(parameters, ConstantTimeLagParameters):
            self.lag_seconds_spin.setValue(parameters.lag_seconds)
        elif isinstance(parameters, AnnularVolumeFlowLagParameters):
            self.annular_volume_spin.setValue(parameters.annular_volume_m3)
            self.flow_rate_spin.setValue(parameters.flow_rate_m3_per_s)
        elif isinstance(parameters, PumpStrokeLagParameters):
            self.annular_volume_spin.setValue(parameters.annular_volume_m3)
            self.pump_output_spin.setValue(parameters.pump_output_m3_per_stroke)
            self.strokes_spin.setValue(parameters.strokes_per_minute)
        elif isinstance(parameters, ControlPointLagParameters):
            self.control_points_edit.setPlainText(
                "; ".join(
                    f"{point.row + 1}:{point.corrected_depth_m:g}"
                    for point in parameters.points
                )
            )
        self._update_method_controls()
        self._preview()

    def _update_method_controls(self) -> None:
        method = self.method_selector.currentData()
        constant = method is LagCorrectionMethod.CONSTANT_TIME
        volume = method is LagCorrectionMethod.ANNULAR_VOLUME_FLOW
        pump = method is LagCorrectionMethod.PUMP_STROKES
        points = method is LagCorrectionMethod.CONTROL_POINTS
        self.lag_seconds_spin.setEnabled(constant)
        self.annular_volume_spin.setEnabled(volume or pump)
        self.flow_rate_spin.setEnabled(volume)
        self.pump_output_spin.setEnabled(pump)
        self.strokes_spin.setEnabled(pump)
        self.control_points_edit.setEnabled(points)
        self.control_hint.setEnabled(points)
        self.time_selector.setEnabled(not points)
        self.policy_selector.setEnabled(not points)

    def _selected_curves(self) -> tuple[str, ...]:
        return tuple(
            str(item.data(Qt.ItemDataRole.UserRole))
            for index in range(self.curve_list.count())
            if (item := self.curve_list.item(index)).checkState() == Qt.CheckState.Checked
        )

    def _parameters(self):
        method = self.method_selector.currentData()
        if method is LagCorrectionMethod.CONSTANT_TIME:
            return ConstantTimeLagParameters(self.lag_seconds_spin.value())
        if method is LagCorrectionMethod.ANNULAR_VOLUME_FLOW:
            return AnnularVolumeFlowLagParameters(
                self.annular_volume_spin.value(), self.flow_rate_spin.value()
            )
        if method is LagCorrectionMethod.PUMP_STROKES:
            return PumpStrokeLagParameters(
                self.annular_volume_spin.value(),
                self.pump_output_spin.value(),
                self.strokes_spin.value(),
            )
        if method is LagCorrectionMethod.CONTROL_POINTS:
            points: list[LagDepthControlPoint] = []
            raw = self.control_points_edit.toPlainText().replace("\n", ";")
            for token in raw.split(";"):
                token = token.strip()
                if not token:
                    continue
                row_text, separator, depth_text = token.partition(":")
                if not separator:
                    raise ValueError(f"Некорректная контрольная точка: {token}")
                row = int(row_text.strip()) - 1
                depth = float(depth_text.strip().replace(",", "."))
                points.append(LagDepthControlPoint(row, depth))
            return ControlPointLagParameters(tuple(points))
        raise ValueError("Не выбран метод lag correction")

    def _request_values(self) -> dict[str, object]:
        curves = self._selected_curves()
        if not curves:
            raise ValueError(self.text["select_curve"])
        depth_index_id = self.depth_selector.currentData()
        method = self.method_selector.currentData()
        time_index_id = self.time_selector.currentData()
        if depth_index_id is None or (
            method is not LagCorrectionMethod.CONTROL_POINTS and time_index_id is None
        ):
            raise ValueError(self.text["select_indexes"])
        return {
            "source_time_index_id": None if time_index_id is None else str(time_index_id),
            "source_depth_index_id": str(depth_index_id),
            "target_curve_ids": curves,
            "method": method,
            "parameters": self._parameters(),
            "aggregation_policy": self.policy_selector.currentData(),
            "created_at": datetime.now(timezone.utc).isoformat(),
            "created_by": self.author_edit.text().strip(),
            "comment": self.comment_edit.text(),
        }

    def _save(self) -> None:
        profile = self._selected_profile()
        try:
            values = self._request_values()
            if profile is None:
                created = self.controller.create_profile(
                    name=self.name_edit.text().strip(),
                    target=self.target_selector.currentData(),
                    **values,
                )
                message = self.text["created"].format(name=created.name)
                selected_id = created.profile_id
            else:
                updated = self.controller.add_revision(
                    profile.profile_id,
                    expected_latest_revision=profile.latest_revision,
                    **values,
                )
                message = self.text["revised"].format(revision=updated.latest_revision)
                selected_id = updated.profile_id
        except (KeyError, TypeError, ValueError, RuntimeError) as exc:
            QMessageBox.warning(self, self.text["title"], str(exc))
            return
        self._refresh_profiles(selected_id)
        QMessageBox.information(self, self.text["title"], message)

    def _activate(self) -> None:
        profile = self._selected_profile()
        revision = self.revision_selector.currentData()
        if profile is None or revision is None:
            return
        try:
            updated = self.controller.activate_revision(
                profile.profile_id,
                int(revision),
                expected_active_revision=profile.active_revision,
            )
        except (KeyError, ValueError, RuntimeError) as exc:
            QMessageBox.warning(self, self.text["title"], str(exc))
            return
        self._refresh_profiles(updated.profile_id)
        QMessageBox.information(
            self,
            self.text["title"],
            self.text["activated"].format(revision=updated.active_revision),
        )

    def _delete(self) -> None:
        profile = self._selected_profile()
        if profile is None:
            return
        answer = QMessageBox.question(
            self, self.text["title"], self.text["confirm_delete"]
        )
        if answer != QMessageBox.StandardButton.Yes:
            return
        try:
            self.controller.delete_profile(profile.profile_id)
        except (KeyError, RuntimeError) as exc:
            QMessageBox.warning(self, self.text["title"], str(exc))
            return
        self._refresh_profiles()

    def _preview(self) -> None:
        profile = self._selected_profile()
        revision = self.revision_selector.currentData()
        if profile is None or revision is None:
            self.preview_table.setRowCount(0)
            self.summary_label.clear()
            return
        try:
            preview = self.controller.preview(profile.profile_id, int(revision))
        except (KeyError, ValueError, RuntimeError) as exc:
            QMessageBox.warning(self, self.text["title"], str(exc))
            return
        shown = min(preview.row_count, 500)
        self.preview_table.setRowCount(shown)
        for row in range(shown):
            values = (
                str(row + 1),
                _format_number(preview.source_depth[row]),
                _format_number(preview.corrected_depth[row]),
                _format_number(preview.lag_seconds[row]),
            )
            for column, value in enumerate(values):
                self.preview_table.setItem(row, column, QTableWidgetItem(value))
        self.preview_table.resizeColumnsToContents()
        self.summary_label.setText(
            self.text["summary"].format(
                rows=preview.row_count,
                valid=preview.valid_count,
                invalid=preview.invalid_count,
            )
        )

    def _select_projection(self, mode: LagCorrectionAxisMode) -> None:
        profile = self._selected_profile()
        revision = self.revision_selector.currentData()
        if profile is None or revision is None:
            return
        try:
            selection = self.controller.select_projection(
                profile.profile_id, mode, int(revision)
            )
        except (KeyError, ValueError, RuntimeError) as exc:
            QMessageBox.warning(self, self.text["title"], str(exc))
            return
        mode_text = (
            self.text["mode_source"]
            if mode is LagCorrectionAxisMode.SOURCE
            else self.text["mode_corrected"]
        )
        QMessageBox.information(
            self,
            self.text["title"],
            self.text["selected"].format(
                mode=mode_text,
                revision=selection.revision,
            ),
        )


def _format_number(value: object) -> str:
    numeric = float(value)
    return "—" if not np.isfinite(numeric) else f"{numeric:.6g}"
