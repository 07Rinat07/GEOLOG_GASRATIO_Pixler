from __future__ import annotations

from pathlib import Path

from PySide6.QtWidgets import (
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFileDialog,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QTextEdit,
    QVBoxLayout,
)

from geoworkbench.project.daily_las_growth_controller import DailyLasGrowthController
from geoworkbench.services.daily_las_growth import DailyLasGrowthPlan
from geoworkbench.services.localization import AppLanguage


class DailyLasGrowthDialog(QDialog):
    """Choose one explicit target dataset and preview a safe daily LAS append."""

    def __init__(
        self,
        controller: DailyLasGrowthController,
        parent=None,
        *,
        language: AppLanguage = AppLanguage.RU,
    ) -> None:
        super().__init__(parent)
        self.controller = controller
        self.language = language.value if isinstance(language, AppLanguage) else str(language)
        self.plan: DailyLasGrowthPlan | None = None
        self.setWindowTitle(self._text("Ежедневное наращивание LAS", "LAS күнделікті өсіру", "Daily LAS growth"))
        self.resize(720, 470)
        root = QVBoxLayout(self)
        info = QLabel(
            self._text(
                "Добавляются только новые строки в явно выбранный dataset. Другие глубинки, временки, формы, значки и комментарии не изменяются.",
                "Тек нақты таңдалған dataset-ке жаңа жолдар қосылады. Басқа тереңдік/уақыт деректері, пішіндер, белгілер және пікірлер өзгермейді.",
                "Only new rows are appended to the explicitly selected dataset. Other depth/time datasets, forms, symbols and comments are not changed.",
            )
        )
        info.setWordWrap(True)
        root.addWidget(info)

        form = QFormLayout()
        self.target_combo = QComboBox()
        for dataset in controller.datasets_for_current_well():
            index = dataset.active_index
            label = f"{dataset.name} — {index.role.value.upper()} / {index.mnemonic}"
            self.target_combo.addItem(label, dataset.dataset_id)
        self.file_input = QLineEdit()
        file_row = QHBoxLayout()
        file_row.addWidget(self.file_input, 1)
        browse = QPushButton(self._text("Выбрать…", "Таңдау…", "Browse…"))
        browse.clicked.connect(self._browse)
        file_row.addWidget(browse)
        form.addRow(self._text("Целевой dataset", "Мақсатты dataset", "Target dataset"), self.target_combo)
        form.addRow(self._text("Новый LAS", "Жаңа LAS", "New LAS"), file_row)
        root.addLayout(form)

        analyze = QPushButton(self._text("Проверить прирост", "Өсімді тексеру", "Analyze growth"))
        analyze.clicked.connect(self._analyze)
        root.addWidget(analyze)
        self.preview = QTextEdit()
        self.preview.setReadOnly(True)
        root.addWidget(self.preview, 1)

        self.buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        self.buttons.button(QDialogButtonBox.StandardButton.Ok).setText(
            self._text("Нарастить", "Өсіру", "Append")
        )
        self.buttons.button(QDialogButtonBox.StandardButton.Ok).setEnabled(False)
        self.buttons.accepted.connect(self._accept)
        self.buttons.rejected.connect(self.reject)
        root.addWidget(self.buttons)
        self.file_input.textChanged.connect(self._invalidate)
        self.target_combo.currentIndexChanged.connect(self._invalidate)

    def _text(self, ru: str, kk: str, en: str) -> str:
        return {"ru": ru, "kk": kk, "en": en}.get(self.language, ru)

    def _browse(self) -> None:
        filename, _ = QFileDialog.getOpenFileName(
            self,
            self.windowTitle(),
            "",
            "LAS (*.las *.LAS)",
        )
        if filename:
            self.file_input.setText(filename)

    def _invalidate(self) -> None:
        self.plan = None
        self.buttons.button(QDialogButtonBox.StandardButton.Ok).setEnabled(False)

    def _analyze(self) -> None:
        dataset_id = self.target_combo.currentData()
        source = Path(self.file_input.text().strip())
        if not isinstance(dataset_id, str) or not source.is_file():
            QMessageBox.warning(
                self,
                self.windowTitle(),
                self._text("Выберите существующий LAS и целевой dataset", "LAS және мақсатты dataset таңдаңыз", "Choose an existing LAS and target dataset"),
            )
            return
        try:
            plan = self.controller.analyze(source, dataset_id)
        except (OSError, RuntimeError, ValueError) as exc:
            self.preview.setPlainText(str(exc))
            QMessageBox.warning(self, self.windowTitle(), str(exc))
            return
        self.plan = plan
        role = plan.index_role.value.upper()
        duplicate = self._text("Да", "Иә", "Yes") if plan.duplicate_source else self._text("Нет", "Жоқ", "No")
        self.preview.setPlainText(
            self._text(
                f"Ось: {role} ({plan.index_mnemonic})\nДиапазон файла: {plan.start_value} … {plan.stop_value}\nНовых строк: {plan.rows_added}\nСовпадающих строк: {plan.rows_skipped}\nФайл уже импортирован: {duplicate}\n\nБудет изменён только выбранный dataset.",
                f"Ось: {role} ({plan.index_mnemonic})\nФайл ауқымы: {plan.start_value} … {plan.stop_value}\nЖаңа жолдар: {plan.rows_added}\nСәйкес жолдар: {plan.rows_skipped}\nФайл бұрын импортталған: {duplicate}\n\nТек таңдалған dataset өзгереді.",
                f"Axis: {role} ({plan.index_mnemonic})\nFile range: {plan.start_value} … {plan.stop_value}\nNew rows: {plan.rows_added}\nMatching rows: {plan.rows_skipped}\nAlready imported: {duplicate}\n\nOnly the selected dataset will change.",
            )
        )
        self.buttons.button(QDialogButtonBox.StandardButton.Ok).setEnabled(True)

    def _accept(self) -> None:
        if self.plan is not None:
            self.accept()
