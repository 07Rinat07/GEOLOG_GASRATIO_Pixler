from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QLabel,
    QMessageBox,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from geoworkbench.domain.models import Well
from geoworkbench.project.canvas_object_transfer_controller import (
    CanvasObjectCollisionPolicy,
    CanvasObjectTransferAction,
    CanvasObjectTransferError,
    CanvasObjectTransferOutcome,
    CanvasObjectTransferPlan,
)
from geoworkbench.project.canvas_object_transfer_workflow import (
    CanvasObjectTransferApplication,
)
from geoworkbench.services.localization import AppLanguage


class CanvasObjectTransferDialog(QDialog):
    """Review an explicit well-level authored-object transfer before persistence."""

    def __init__(
        self,
        application: CanvasObjectTransferApplication,
        target_well_id: str,
        *,
        language: AppLanguage = AppLanguage.RU,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.application = application
        self.target_well_id = target_well_id
        self.language = language
        self.plan: CanvasObjectTransferPlan | None = None
        self.outcome: CanvasObjectTransferOutcome | None = None
        self._source_wells: dict[str, Well] = {
            well.well_id: well
            for well in application.available_source_wells(target_well_id)
        }

        self.setWindowTitle(
            self._text(
                "Перенос пользовательских рисунков",
                "Пайдаланушы суреттерін көшіру",
                "Transfer authored drawings",
            )
        )
        self.resize(900, 650)
        root = QVBoxLayout(self)

        summary = QLabel(
            self._text(
                "Предварительный просмотр ничего не записывает. Переносятся только явно "
                "выбранные объекты уровня скважины; существующие рисунки не перезаписываются.",
                "Алдын ала қарау ештеңе жазбайды. Тек нақты таңдалған ұңғыма деңгейіндегі "
                "объектілер көшіріледі; бар суреттер қайта жазылмайды.",
                "Preview does not write anything. Only explicitly selected well-level "
                "objects are copied; existing drawings are never overwritten.",
            )
        )
        summary.setWordWrap(True)
        summary.setObjectName("canvas-transfer-safety-summary")
        root.addWidget(summary)

        form = QFormLayout()
        self.source_combo = QComboBox()
        for well in self._source_wells.values():
            self.source_combo.addItem(
                f"{well.name} — {len(well.canvas_objects)}",
                well.well_id,
            )
        self.source_combo.currentIndexChanged.connect(self._source_changed)
        form.addRow(
            self._text("Скважина-источник", "Бастапқы ұңғыма", "Source well"),
            self.source_combo,
        )

        self.collision_combo = QComboBox()
        self.collision_combo.addItem(
            self._text(
                "Остановить при конфликте ID",
                "ID қақтығысында тоқтату",
                "Stop on ID conflict",
            ),
            CanvasObjectCollisionPolicy.ERROR,
        )
        self.collision_combo.addItem(
            self._text(
                "Пропустить существующие ID",
                "Бар ID-лерді өткізіп жіберу",
                "Skip existing IDs",
            ),
            CanvasObjectCollisionPolicy.SKIP,
        )
        self.collision_combo.addItem(
            self._text(
                "Создать копию с новым ID",
                "Жаңа ID-мен көшірме жасау",
                "Create a copy with a new ID",
            ),
            CanvasObjectCollisionPolicy.RENAME,
        )
        self.collision_combo.currentIndexChanged.connect(self._policy_changed)
        form.addRow(
            self._text("Конфликты ID", "ID қақтығыстары", "ID conflicts"),
            self.collision_combo,
        )
        root.addLayout(form)

        self.source_table = QTableWidget(0, 6)
        self.source_table.setObjectName("canvas-transfer-source-table")
        self.source_table.setHorizontalHeaderLabels(
            [
                self._text("Выбрать", "Таңдау", "Select"),
                "ID",
                self._text("Тип", "Түрі", "Type"),
                self._text("Якорь", "Зәкір", "Anchor"),
                self._text("Трек", "Трек", "Track"),
                self._text("Параметр", "Параметр", "Parameter"),
            ]
        )
        root.addWidget(self.source_table, 1)

        self.preview_button = QPushButton(
            self._text("Проверить перенос", "Көшіруді тексеру", "Preview transfer")
        )
        self.preview_button.clicked.connect(self._analyze)
        root.addWidget(self.preview_button)

        self.counts_label = QLabel()
        self.counts_label.setObjectName("canvas-transfer-counts")
        root.addWidget(self.counts_label)

        self.preview_table = QTableWidget(0, 4)
        self.preview_table.setObjectName("canvas-transfer-preview-table")
        self.preview_table.setHorizontalHeaderLabels(
            [
                self._text("Исходный ID", "Бастапқы ID", "Source ID"),
                self._text("Целевой ID", "Мақсатты ID", "Target ID"),
                self._text("Тип", "Түрі", "Type"),
                self._text("Действие", "Әрекет", "Action"),
            ]
        )
        root.addWidget(self.preview_table, 1)

        self.buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        self.buttons.button(QDialogButtonBox.StandardButton.Ok).setText(
            self._text("Перенести", "Көшіру", "Transfer")
        )
        self.buttons.button(QDialogButtonBox.StandardButton.Ok).setEnabled(False)
        self.buttons.accepted.connect(self._accept)
        self.buttons.rejected.connect(self.reject)
        root.addWidget(self.buttons)

        self._reload_source_objects()
        if not self._source_wells:
            self.preview_button.setEnabled(False)
            self.counts_label.setText(
                self._text(
                    "Нет других скважин с пользовательскими рисунками.",
                    "Пайдаланушы суреттері бар басқа ұңғымалар жоқ.",
                    "No other wells contain authored drawings.",
                )
            )

    def selected_object_ids(self) -> tuple[str, ...]:
        selected: list[str] = []
        for row in range(self.source_table.rowCount()):
            choice = self.source_table.item(row, 0)
            if choice is None or choice.checkState() is not Qt.CheckState.Checked:
                continue
            object_id = choice.data(Qt.ItemDataRole.UserRole)
            if isinstance(object_id, str):
                selected.append(object_id)
        return tuple(selected)

    def _source_changed(self, _index: int = -1) -> None:
        self._invalidate()
        self._reload_source_objects()

    def _policy_changed(self, _index: int = -1) -> None:
        self._invalidate()

    def _reload_source_objects(self) -> None:
        source_id = self.source_combo.currentData()
        well = self._source_wells.get(source_id) if isinstance(source_id, str) else None
        objects = () if well is None else tuple(well.canvas_objects)
        self.source_table.setRowCount(len(objects))
        for row, item in enumerate(objects):
            choice = QTableWidgetItem()
            choice.setFlags(Qt.ItemFlag.ItemIsEnabled | Qt.ItemFlag.ItemIsUserCheckable)
            choice.setCheckState(Qt.CheckState.Unchecked)
            choice.setData(Qt.ItemDataRole.UserRole, item.object_id)
            self.source_table.setItem(row, 0, choice)
            values = (
                item.object_id,
                item.object_type,
                item.anchor_type,
                item.track_id or "—",
                item.parameter_mnemonic or "—",
            )
            for column, value in enumerate(values, 1):
                cell = QTableWidgetItem(value)
                cell.setFlags(Qt.ItemFlag.ItemIsEnabled | Qt.ItemFlag.ItemIsSelectable)
                self.source_table.setItem(row, column, cell)
        self.source_table.resizeColumnsToContents()

    def _analyze(self) -> None:
        self._invalidate()
        source_well_id = self.source_combo.currentData()
        if not isinstance(source_well_id, str):
            return
        object_ids = self.selected_object_ids()
        if not object_ids:
            QMessageBox.information(
                self,
                self.windowTitle(),
                self._text(
                    "Выберите хотя бы один рисунок.",
                    "Кемінде бір суретті таңдаңыз.",
                    "Select at least one drawing.",
                ),
            )
            return
        policy = self.collision_combo.currentData()
        if not isinstance(policy, CanvasObjectCollisionPolicy):
            QMessageBox.warning(
                self,
                self.windowTitle(),
                self._text(
                    "Не выбрана политика конфликтов ID.",
                    "ID қақтығыстары саясаты таңдалмаған.",
                    "No ID-conflict policy is selected.",
                ),
            )
            return
        try:
            plan = self.application.analyze(
                source_well_id,
                self.target_well_id,
                object_ids=object_ids,
                collision_policy=policy,
            )
        except CanvasObjectTransferError as exc:
            QMessageBox.warning(self, self.windowTitle(), str(exc))
            return
        self.plan = plan
        self._render_plan(plan)
        self.buttons.button(QDialogButtonBox.StandardButton.Ok).setEnabled(True)

    def _render_plan(self, plan: CanvasObjectTransferPlan) -> None:
        self.preview_table.setRowCount(len(plan.items))
        for row, item in enumerate(plan.items):
            action = {
                CanvasObjectTransferAction.COPY: self._text(
                    "Копировать", "Көшіру", "Copy"
                ),
                CanvasObjectTransferAction.SKIP: self._text(
                    "Пропустить", "Өткізу", "Skip"
                ),
                CanvasObjectTransferAction.RENAME: self._text(
                    "Копировать с новым ID", "Жаңа ID-мен көшіру", "Copy with new ID"
                ),
            }[item.action]
            for column, value in enumerate(
                (
                    item.source_object_id,
                    item.target_object_id,
                    item.object_type,
                    action,
                )
            ):
                cell = QTableWidgetItem(value)
                cell.setFlags(Qt.ItemFlag.ItemIsEnabled | Qt.ItemFlag.ItemIsSelectable)
                self.preview_table.setItem(row, column, cell)
        self.preview_table.resizeColumnsToContents()
        self.counts_label.setText(
            self._text(
                f"К переносу: {plan.copy_count}; пропущено: {plan.skipped_count}; "
                f"конфликтов: {plan.collision_count}",
                f"Көшіруге: {plan.copy_count}; өткізілді: {plan.skipped_count}; "
                f"қақтығыстар: {plan.collision_count}",
                f"To transfer: {plan.copy_count}; skipped: {plan.skipped_count}; "
                f"conflicts: {plan.collision_count}",
            )
        )

    def _accept(self) -> None:
        if self.plan is None:
            return
        try:
            self.outcome = self.application.apply(self.plan)
        except CanvasObjectTransferError as exc:
            self._invalidate(reset_application=False)
            QMessageBox.warning(self, self.windowTitle(), str(exc))
            return
        self.accept()

    def reject(self) -> None:
        self.application.reset_state()
        super().reject()

    def _invalidate(self, *, reset_application: bool = True) -> None:
        self.plan = None
        self.outcome = None
        self.preview_table.setRowCount(0)
        self.counts_label.clear()
        self.buttons.button(QDialogButtonBox.StandardButton.Ok).setEnabled(False)
        if reset_application:
            self.application.reset_state()

    def _text(self, ru: str, kk: str, en: str) -> str:
        if self.language is AppLanguage.KK:
            return kk
        if self.language is AppLanguage.EN:
            return en
        return ru
