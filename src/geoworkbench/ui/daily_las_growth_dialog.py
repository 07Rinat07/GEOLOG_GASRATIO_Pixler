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
from geoworkbench.services.local_las_folder import (
    LocalLasCandidate,
    LocalLasFolderError,
    LocalLasFolderProvider,
)
from geoworkbench.ui.navigation_organization import open_help_for_widget


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
        self._folder_candidates: tuple[LocalLasCandidate, ...] = ()
        self.setWindowTitle(self._text("Ежедневное наращивание LAS", "LAS күнделікті өсіру", "Daily LAS growth"))
        self.resize(720, 470)
        root = QVBoxLayout(self)
        self.info_label = QLabel(
            self._text(
                "Откройте рабочий .geologpkg и добавляйте только новые строки в явно выбранный dataset. Формы, геология, значки и комментарии не заменяются.",
                "Жұмыс .geologpkg жобасын ашып, тек нақты таңдалған dataset-ке жаңа жолдарды қосыңыз. Пішіндер, геология, белгілер мен пікірлер ауыстырылмайды.",
                "Open the working .geologpkg and append only new rows to the explicitly selected dataset. Forms, geology, symbols, and comments are not replaced.",
            )
        )
        self.info_label.setObjectName("daily-las-safety-summary")
        self.info_label.setWordWrap(True)
        assistant_row = QHBoxLayout()
        assistant_row.addWidget(self.info_label, 1)
        self.workflow_help_button = QPushButton(
            self._text(
                "Помощник: как наращивать безопасно",
                "Көмекші: қауіпсіз толықтыру тәртібі",
                "Assistant: safe daily append",
            )
        )
        self.workflow_help_button.setObjectName("daily-las-workflow-help")
        self.workflow_help_button.setToolTip(
            self._text(
                "Открыть пошаговую инструкцию: первый LAS, ежедневный прирост, три языка, сохранение и перенос.",
                "Қадамдық нұсқаулықты ашу: алғашқы LAS, күнделікті өсім, үш тіл, сақтау және тасымалдау.",
                "Open the step-by-step guide for the first LAS, daily growth, three languages, saving, and transfer.",
            )
        )
        self.workflow_help_button.clicked.connect(
            lambda: open_help_for_widget(self, "project")
        )
        assistant_row.addWidget(self.workflow_help_button)
        root.addLayout(assistant_row)

        form = QFormLayout()
        self.target_combo = QComboBox()
        self.target_combo.setToolTip(
            self._text(
                "Выберите основной dataset этой скважины. Его идентификатор и ручные слои сохранятся.",
                "Осы ұңғыманың негізгі dataset-ін таңдаңыз. Оның идентификаторы мен қолмен енгізілген қабаттары сақталады.",
                "Select this well's main dataset. Its identity and manual layers will be preserved.",
            )
        )
        for dataset in controller.datasets_for_current_well():
            index = dataset.active_index
            label = f"{dataset.name} — {index.role.value.upper()} / {index.mnemonic}"
            self.target_combo.addItem(label, dataset.dataset_id)
        self.file_input = QLineEdit()
        self.file_input.setPlaceholderText(
            self._text(
                "Сегодняшний LAS или накопительный LAS",
                "Бүгінгі LAS немесе жинақталған LAS",
                "Today's LAS or a cumulative LAS",
            )
        )
        self.file_input.setToolTip(
            self._text(
                "Не выбирайте .geologpkg: здесь нужен только новый исходный LAS с теми же кривыми и единицами.",
                ".geologpkg таңдамаңыз: мұнда қисықтары мен бірліктері сәйкес жаңа бастапқы LAS қажет.",
                "Do not select a .geologpkg here; choose only a new source LAS with matching curves and units.",
            )
        )
        file_row = QHBoxLayout()
        file_row.addWidget(self.file_input, 1)
        browse = QPushButton(self._text("Выбрать…", "Таңдау…", "Browse…"))
        browse.clicked.connect(self._browse)
        file_row.addWidget(browse)
        form.addRow(self._text("Целевой dataset", "Мақсатты dataset", "Target dataset"), self.target_combo)
        self.folder_input = QLineEdit()
        self.folder_input.setPlaceholderText(
            self._text(
                "Локальная папка, синхронизируемая серверным клиентом",
                "Сервер клиенті синхрондайтын жергілікті қалта",
                "Local folder synchronized by the server client",
            )
        )
        self.folder_input.setToolTip(
            self._text(
                "Приложение только читает эту папку. Дождитесь окончания серверной синхронизации перед обновлением списка.",
                "Қолданба бұл қалтаны тек оқиды. Тізімді жаңартпас бұрын сервер синхрондауының аяқталуын күтіңіз.",
                "The application only reads this folder. Wait for server synchronization to finish before refreshing the list.",
            )
        )
        folder_row = QHBoxLayout()
        folder_row.addWidget(self.folder_input, 1)
        folder_browse = QPushButton(
            self._text("Папка…", "Қалта…", "Folder…")
        )
        folder_browse.clicked.connect(self._browse_folder)
        folder_row.addWidget(folder_browse)
        refresh = QPushButton(self._text("Обновить", "Жаңарту", "Refresh"))
        refresh.clicked.connect(self._refresh_folder)
        folder_row.addWidget(refresh)
        form.addRow(
            self._text(
                "Синхронизируемая папка", "Синхрондалатын қалта", "Synchronized folder"
            ),
            folder_row,
        )
        self.folder_files = QComboBox()
        self.folder_files.setToolTip(
            self._text(
                "Список отсортирован по времени изменения. Всегда сверяйте имя и диапазон в предварительном анализе.",
                "Тізім өзгерту уақыты бойынша сұрыпталған. Алдын ала талдауда атау мен ауқымды әрқашан тексеріңіз.",
                "The list is sorted by modification time. Always verify the name and range in the preview.",
            )
        )
        self.folder_files.currentIndexChanged.connect(self._select_folder_candidate)
        form.addRow(
            self._text("Доступные LAS", "Қолжетімді LAS", "Available LAS"),
            self.folder_files,
        )
        form.addRow(self._text("Новый LAS", "Жаңа LAS", "New LAS"), file_row)
        root.addLayout(form)

        self.analyze_button = QPushButton(
            self._text("Проверить прирост", "Өсімді тексеру", "Analyze growth")
        )
        self.analyze_button.setToolTip(
            self._text(
                "Проверить ось, скважину, схему, единицы, перекрытие, SHA-256 и число новых строк без изменения проекта.",
                "Жобаны өзгертпей осьті, ұңғыманы, схеманы, бірліктерді, қабаттасуды, SHA-256 және жаңа жолдар санын тексеру.",
                "Validate the axis, well, schema, units, overlap, SHA-256, and new-row count without changing the project.",
            )
        )
        self.analyze_button.clicked.connect(self._analyze)
        root.addWidget(self.analyze_button)
        self.preview = QTextEdit()
        self.preview.setObjectName("daily-las-growth-preview")
        self.preview.setReadOnly(True)
        self.preview.setPlainText(
            self._text(
                "1. Выберите основной dataset.\n2. Выберите LAS.\n3. Нажмите «Проверить прирост».\n4. Наращивайте только после проверки диапазона и числа строк.",
                "1. Негізгі dataset-ті таңдаңыз.\n2. LAS таңдаңыз.\n3. «Өсімді тексеру» басыңыз.\n4. Ауқым мен жолдар санын тексергеннен кейін ғана толықтырыңыз.",
                "1. Select the main dataset.\n2. Select the LAS.\n3. Press Analyze growth.\n4. Append only after checking the range and row counts.",
            )
        )
        root.addWidget(self.preview, 1)

        self.buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        self.buttons.button(QDialogButtonBox.StandardButton.Ok).setText(
            self._text("Нарастить", "Өсіру", "Append")
        )
        append_button = self.buttons.button(QDialogButtonBox.StandardButton.Ok)
        append_button.setEnabled(False)
        append_button.setToolTip(
            self._text(
                "После наращивания обязательно сохраните .geologpkg через Ctrl+S.",
                "Толықтырғаннан кейін .geologpkg жобасын Ctrl+S арқылы міндетті түрде сақтаңыз.",
                "After appending, save the .geologpkg with Ctrl+S.",
            )
        )
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

    def _browse_folder(self) -> None:
        folder = QFileDialog.getExistingDirectory(
            self,
            self._text(
                "Выберите синхронизируемую папку LAS",
                "LAS синхрондалатын қалтаны таңдаңыз",
                "Choose synchronized LAS folder",
            ),
            self.folder_input.text().strip(),
        )
        if folder:
            self.folder_input.setText(folder)
            self._refresh_folder()

    def _refresh_folder(self) -> None:
        folder = self.folder_input.text().strip()
        if not folder:
            return
        try:
            self._folder_candidates = LocalLasFolderProvider(folder).discover()
        except (OSError, ValueError, LocalLasFolderError) as exc:
            self._folder_candidates = ()
            self.folder_files.clear()
            QMessageBox.warning(self, self.windowTitle(), str(exc))
            return
        self.folder_files.clear()
        for candidate in self._folder_candidates:
            self.folder_files.addItem(
                f"{candidate.relative_path} — {candidate.size_bytes} B — {candidate.modified_at}",
                candidate.sha256,
            )
        if not self._folder_candidates:
            self.preview.setPlainText(
                self._text(
                    "В папке нет LAS-файлов.",
                    "Қалтада LAS файлдары жоқ.",
                    "No LAS files were found in the folder.",
                )
            )

    def _select_folder_candidate(self, index: int) -> None:
        if 0 <= index < len(self._folder_candidates):
            self.file_input.setText(str(self._folder_candidates[index].path))

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
            candidate = next(
                (item for item in self._folder_candidates if item.path == source.resolve()),
                None,
            )
            if candidate is not None:
                LocalLasFolderProvider(self.folder_input.text().strip()).verify(candidate)
                plan = self.controller.analyze(
                    source,
                    dataset_id,
                    provider_kind=LocalLasFolderProvider.provider_kind,
                    provider_location=(
                        f"{self.folder_input.text().strip()}::{candidate.relative_path}"
                    ),
                )
            else:
                plan = self.controller.analyze(source, dataset_id)
        except (OSError, RuntimeError, ValueError) as exc:
            self.preview.setPlainText(str(exc))
            QMessageBox.warning(self, self.windowTitle(), str(exc))
            return
        self.plan = plan
        role = plan.index_role.value.upper()
        duplicate = self._text("Да", "Иә", "Yes") if plan.duplicate_source else self._text("Нет", "Жоқ", "No")
        next_step = (
            self._text(
                "Файл уже учтён. Повторное подтверждение безопасно и не изменит dataset.",
                "Файл бұрын есепке алынған. Қайта растау қауіпсіз және dataset-ті өзгертпейді.",
                "The file is already recorded. Confirming again is safe and will not change the dataset.",
            )
            if plan.duplicate_source or not plan.changes_data
            else self._text(
                "Если диапазон и строки верны, нажмите «Нарастить», сразу сохраните .geologpkg через Ctrl+S и повторите нужные расчёты.",
                "Ауқым мен жолдар дұрыс болса, «Өсіру» басып, .geologpkg жобасын бірден Ctrl+S арқылы сақтаңыз және қажетті есептеулерді қайталаңыз.",
                "If the range and rows are correct, press Append, immediately save the .geologpkg with Ctrl+S, and rerun the required calculations.",
            )
        )
        self.preview.setPlainText(
            self._text(
                f"Ось: {role} ({plan.index_mnemonic})\nДиапазон файла: {plan.start_value} … {plan.stop_value}\nНовых строк: {plan.rows_added}\nСовпадающих строк: {plan.rows_skipped}\nФайл уже импортирован: {duplicate}\n\nБудет изменён только выбранный dataset.\n\n{next_step}",
                f"Ось: {role} ({plan.index_mnemonic})\nФайл ауқымы: {plan.start_value} … {plan.stop_value}\nЖаңа жолдар: {plan.rows_added}\nСәйкес жолдар: {plan.rows_skipped}\nФайл бұрын импортталған: {duplicate}\n\nТек таңдалған dataset өзгереді.\n\n{next_step}",
                f"Axis: {role} ({plan.index_mnemonic})\nFile range: {plan.start_value} … {plan.stop_value}\nNew rows: {plan.rows_added}\nMatching rows: {plan.rows_skipped}\nAlready imported: {duplicate}\n\nOnly the selected dataset will change.\n\n{next_step}",
            )
        )
        self.buttons.button(QDialogButtonBox.StandardButton.Ok).setEnabled(True)

    def _accept(self) -> None:
        if self.plan is not None:
            self.accept()
