from __future__ import annotations

from collections.abc import Callable

from PySide6.QtCore import QSize, Qt
from PySide6.QtGui import QIcon, QPixmap
from PySide6.QtWidgets import (
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QHBoxLayout,
    QInputDialog,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QMessageBox,
    QPushButton,
    QSplitter,
    QStackedWidget,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from geoworkbench.form_constructor.asset_install import (
    install_assets_into_project,
    load_factory_constructor_registry,
)
from geoworkbench.form_constructor.asset_registry import AssetDefinition
from geoworkbench.printing.masterlog_output import MasterlogOutputSettings
from geoworkbench.printing.masterlog_preflight import analyze_masterlog_output
from geoworkbench.printing.masterlog_renderer import masterlog_depth_range
from geoworkbench.project.masterlog_template_controller import MasterlogTemplateController
from geoworkbench.services.localization import AppLanguage, Localizer
from geoworkbench.ui.masterlog_assets_dialog import MasterlogAssetsDialog
from geoworkbench.ui.masterlog_columns_dialog import MasterlogColumnsDialog
from geoworkbench.ui.masterlog_curve_mapping_dialog import MasterlogCurveMappingDialog
from geoworkbench.ui.masterlog_header_dialog import MasterlogHeaderDialog
from geoworkbench.ui.masterlog_page_dialog import MasterlogPageDialog
from geoworkbench.ui.masterlog_preview_dialog import MasterlogPreviewDialog
from geoworkbench.ui.masterlog_symbols_dialog import MasterlogSymbolsDialog
from geoworkbench.project.masterlog_symbol_controller import MasterlogSymbolController
from geoworkbench.printing.masterlog_presets import BUILTIN_MASTERLOG_FORM_PRESETS
from geoworkbench.ui.collapsible_section import CollapsibleSection


_TEXT = {
    AppLanguage.RU: {
        "title": "Конструктор форм, шапок и печати",
        "tablet_forms": "Формы планшета",
        "print_forms": "Печатные формы и шапки",
        "assets": "Литотипы и обозначения",
        "check": "Проверка перед печатью",
        "open_forms": "Открыть менеджер форм",
        "forms_hint": (
            "Структура экранных форм редактируется существующим редактором дорожек. "
            "Конструктор объединяет его с шапками, печатью, ресурсами и предварительным просмотром."
        ),
        "select_template": "Выберите печатную форму.",
        "header": "Редактор шапки",
        "columns": "Колонки формы",
        "mapping": "Сопоставление параметров",
        "page": "Страница и масштаб",
        "preview": "Предварительный просмотр",
        "symbols": "Глубинные обозначения",
        "project_images": "Изображения проекта",
        "refresh": "Обновить",
        "search": "Поиск по названию, псевдониму или ID...",
        "all": "Все",
        "lithology": "Породы и литотипы",
        "depth_symbols": "Условные обозначения",
        "install_selected": "Добавить выбранное в проект",
        "install_visible": "Добавить весь показанный набор",
        "installed": "Добавлено изображений: {images}; пород: {lithotypes}.",
        "asset_count": "Показано: {shown} из {total}",
        "no_template": "В проекте пока нет печатных форм. Создайте форму в разделе шаблонов Masterlog.",
        "preflight_run": "Проверить выбранную форму",
        "preflight_no_data": "Для проверки откройте LAS и выберите скважину.",
        "preflight_ok": "Критических проблем не найдено.",
        "workflow_hint": "Выберите раздел слева. Основные действия показаны сразу, дополнительные настройки свёрнуты.",
        "ready_presets": "Готовые образцы",
        "project_templates": "Пользовательские печатные формы",
        "create_from_preset": "Создать пользовательскую копию",
        "preset_hint": "Готовые шапки и формы. Выберите образец и создайте редактируемую копию в проекте.",
        "primary_actions": "Основные действия",
        "advanced_actions": "Дополнительные настройки",
    },
    AppLanguage.KK: {
        "title": "Пішіндер, тақырыптар және баспа конструкторы",
        "tablet_forms": "Планшет пішіндері",
        "print_forms": "Баспа пішіндері мен тақырыптар",
        "assets": "Литотиптер мен белгілер",
        "check": "Баспа алдындағы тексеру",
        "open_forms": "Пішіндер менеджерін ашу",
        "forms_hint": (
            "Экран пішіндерінің құрылымы қолданыстағы жол редакторында өңделеді. "
            "Конструктор оны тақырыптармен, баспамен, ресурстармен және алдын ала қараумен біріктіреді."
        ),
        "select_template": "Баспа пішінін таңдаңыз.",
        "header": "Тақырып редакторы",
        "columns": "Пішін бағандары",
        "mapping": "Параметрлерді сәйкестендіру",
        "page": "Парақ және масштаб",
        "preview": "Алдын ала қарау",
        "symbols": "Тереңдік белгілері",
        "project_images": "Жоба суреттері",
        "refresh": "Жаңарту",
        "search": "Атау, бүркеншік ат немесе ID бойынша іздеу...",
        "all": "Барлығы",
        "lithology": "Тау жыныстары мен литотиптер",
        "depth_symbols": "Шартты белгілер",
        "install_selected": "Таңдалғанын жобаға қосу",
        "install_visible": "Көрсетілген жиынның бәрін қосу",
        "installed": "Суреттер қосылды: {images}; жыныстар: {lithotypes}.",
        "asset_count": "Көрсетілді: {shown} / {total}",
        "no_template": "Жобада баспа пішіндері жоқ. Masterlog үлгілерінен пішін жасаңыз.",
        "preflight_run": "Таңдалған пішінді тексеру",
        "preflight_no_data": "Тексеру үшін LAS ашып, ұңғыманы таңдаңыз.",
        "preflight_ok": "Маңызды ақаулар табылған жоқ.",
        "workflow_hint": "Сол жақтан бөлімді таңдаңыз. Негізгі әрекеттер бірден көрсетіледі, қосымша баптаулар жиналған.",
        "ready_presets": "Дайын үлгілер",
        "project_templates": "Пайдаланушы баспа пішіндері",
        "create_from_preset": "Пайдаланушы көшірмесін жасау",
        "preset_hint": "Дайын тақырыптар мен пішіндер. Үлгіні таңдап, жобада өңделетін көшірме жасаңыз.",
        "primary_actions": "Негізгі әрекеттер",
        "advanced_actions": "Қосымша баптаулар",
    },
    AppLanguage.EN: {
        "title": "Form, header and print constructor",
        "tablet_forms": "Tablet forms",
        "print_forms": "Print forms and headers",
        "assets": "Lithotypes and symbols",
        "check": "Preflight",
        "open_forms": "Open form manager",
        "forms_hint": (
            "Screen-form structure is edited by the existing track editor. The constructor unifies it "
            "with headers, print output, resources and preview."
        ),
        "select_template": "Select a print form.",
        "header": "Header editor",
        "columns": "Form columns",
        "mapping": "Parameter mapping",
        "page": "Page and scale",
        "preview": "Preview",
        "symbols": "Depth symbols",
        "project_images": "Project images",
        "refresh": "Refresh",
        "search": "Search by name, alias or ID...",
        "all": "All",
        "lithology": "Rocks and lithotypes",
        "depth_symbols": "Symbols",
        "install_selected": "Add selected to project",
        "install_visible": "Add all visible assets",
        "installed": "Images added: {images}; lithotypes: {lithotypes}.",
        "asset_count": "Showing {shown} of {total}",
        "no_template": "The project has no print forms yet. Create one from the Masterlog templates.",
        "preflight_run": "Check selected form",
        "preflight_no_data": "Open a LAS file and select a well before checking.",
        "preflight_ok": "No critical issues found.",
        "workflow_hint": "Choose a section on the left. Primary actions stay visible; advanced settings are collapsed.",
        "ready_presets": "Ready presets",
        "project_templates": "User print forms",
        "create_from_preset": "Create editable copy",
        "preset_hint": "Ready headers and forms. Select a preset and create an editable project copy.",
        "primary_actions": "Primary actions",
        "advanced_actions": "Advanced settings",
    },
}


class UniversalConstructorDialog(QDialog):
    """Unified entry point for tablet forms, WYSIWYG headers, assets and print checks."""

    def __init__(
        self,
        controller: MasterlogTemplateController,
        parent=None,
        *,
        language: AppLanguage = AppLanguage.RU,
        open_form_manager: Callable[[], None] | None = None,
        open_template_manager: Callable[[], None] | None = None,
    ) -> None:
        super().__init__(parent)
        self.controller = controller
        self.language = language
        self.localizer = Localizer.create(language)
        self.open_form_manager_callback = open_form_manager
        self.open_template_manager_callback = open_template_manager
        self.registry = load_factory_constructor_registry()
        # Factory lithotypes are exposed by LithotypeCatalogController as a
        # read-only standard layer and therefore are not copied into every
        # project.  Depth symbols are small project image assets and are installed
        # idempotently so the symbol editor can use them immediately.
        install_assets_into_project(
            self.controller.session,
            self.registry.all(kind="depth_symbol"),
        )
        self._visible_assets: tuple[AssetDefinition, ...] = ()
        self.setWindowTitle(_TEXT[language]["title"])
        self.setMinimumSize(1020, 680)
        self.resize(1320, 840)
        self.setStyleSheet(
            "QDialog { background: #f1f5f9; }"
            "QListWidget, QTextEdit { background: white; border: 1px solid #cbd5e1; "
            "border-radius: 7px; }"
            "QPushButton { min-height: 31px; padding: 4px 10px; }"
            "QPushButton#constructor-primary { background: #2563eb; color: white; "
            "font-weight: 600; border: 0; border-radius: 6px; }"
            "QPushButton#constructor-primary:hover { background: #1d4ed8; }"
        )

        title = QLabel(_TEXT[language]["title"])
        title.setStyleSheet("font-size: 20px; font-weight: 700; color: #0f172a;")
        workflow = QLabel(_TEXT[language]["workflow_hint"])
        workflow.setWordWrap(True)
        workflow.setStyleSheet("color: #475569; padding-bottom: 4px;")

        self.navigation = QListWidget()
        self.navigation.setObjectName("constructor-navigation")
        self.navigation.setFixedWidth(245)
        self.navigation.setSpacing(3)
        for caption in (
            _TEXT[language]["tablet_forms"],
            _TEXT[language]["print_forms"],
            _TEXT[language]["assets"],
            _TEXT[language]["check"],
        ):
            item = QListWidgetItem(caption)
            item.setSizeHint(QSize(220, 44))
            self.navigation.addItem(item)
        self.navigation.setToolTip(_TEXT[language]["workflow_hint"])

        self.pages = QStackedWidget()
        self.pages.addWidget(self._build_tablet_forms_tab())
        self.pages.addWidget(self._build_print_forms_tab())
        self.pages.addWidget(self._build_assets_tab())
        self.pages.addWidget(self._build_preflight_tab())
        # Compatibility alias for extensions that used the former tab object.
        self.tabs = self.pages
        self.navigation.currentRowChanged.connect(self.pages.setCurrentIndex)
        self.navigation.setCurrentRow(0)

        splitter = QSplitter(Qt.Orientation.Horizontal)
        splitter.setChildrenCollapsible(False)
        splitter.addWidget(self.navigation)
        splitter.addWidget(self.pages)
        splitter.setSizes([245, 1000])

        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Close)
        buttons.rejected.connect(self.reject)
        buttons.button(QDialogButtonBox.StandardButton.Close).clicked.connect(self.accept)
        layout = QVBoxLayout(self)
        layout.addWidget(title)
        layout.addWidget(workflow)
        layout.addWidget(splitter, 1)
        layout.addWidget(buttons)
        self._populate_preset_gallery()
        self.refresh_templates()
        self._filter_assets()
        for button in self.findChildren(QPushButton):
            if not button.toolTip().strip():
                button.setToolTip(button.text().replace("&", ""))
            if not button.statusTip().strip():
                button.setStatusTip(button.toolTip())

    def _build_tablet_forms_tab(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)
        hint = QLabel(_TEXT[self.language]["forms_hint"])
        hint.setWordWrap(True)
        layout.addWidget(hint)
        open_button = QPushButton(_TEXT[self.language]["open_forms"])
        open_button.setMinimumHeight(42)
        open_button.clicked.connect(self._open_form_manager)
        layout.addWidget(open_button)
        layout.addStretch(1)
        return page

    def _build_print_forms_tab(self) -> QWidget:
        page = QWidget()
        root = QHBoxLayout(page)
        root.setContentsMargins(0, 0, 0, 0)

        left_widget = QWidget()
        left = QVBoxLayout(left_widget)
        preset_title = QLabel(_TEXT[self.language]["ready_presets"])
        preset_title.setStyleSheet("font-weight: 700; color: #0f172a;")
        left.addWidget(preset_title)
        preset_hint = QLabel(_TEXT[self.language]["preset_hint"])
        preset_hint.setWordWrap(True)
        preset_hint.setStyleSheet("color: #64748b;")
        left.addWidget(preset_hint)
        self.preset_list = QListWidget()
        self.preset_list.setToolTip(_TEXT[self.language]["preset_hint"])
        self.preset_list.currentItemChanged.connect(lambda *_: self._update_preset_summary())
        self.preset_list.itemDoubleClicked.connect(lambda *_: self._create_from_selected_preset())
        left.addWidget(self.preset_list, 1)
        create_preset = QPushButton(_TEXT[self.language]["create_from_preset"])
        create_preset.setObjectName("constructor-primary")
        create_preset.setToolTip(_TEXT[self.language]["preset_hint"])
        create_preset.clicked.connect(self._create_from_selected_preset)
        left.addWidget(create_preset)

        project_title = QLabel(_TEXT[self.language]["project_templates"])
        project_title.setStyleSheet("font-weight: 700; color: #0f172a; margin-top: 8px;")
        left.addWidget(project_title)
        self.template_list = QListWidget()
        self.template_list.setToolTip(
            self.localizer.text("masterlog_templates.select")
        )
        self.template_list.currentItemChanged.connect(lambda *_: self._update_template_summary())
        self.template_list.itemDoubleClicked.connect(lambda *_: self._edit_header())
        left.addWidget(self.template_list, 1)
        root.addWidget(left_widget, 5)

        right_widget = QWidget()
        right = QVBoxLayout(right_widget)
        self.template_summary = QTextEdit()
        self.template_summary.setReadOnly(True)
        self.template_summary.setToolTip(
            _TEXT[self.language]["select_template"]
        )
        right.addWidget(self.template_summary, 1)

        primary_widget = QWidget()
        primary = QHBoxLayout(primary_widget)
        primary.setContentsMargins(6, 4, 6, 4)
        for caption, callback, tooltip in (
            (_TEXT[self.language]["header"], self._edit_header, _TEXT[self.language]["header"]),
            (_TEXT[self.language]["preview"], self._preview, _TEXT[self.language]["preview"]),
        ):
            button = QPushButton(caption)
            button.setObjectName("constructor-primary")
            button.setToolTip(tooltip)
            button.clicked.connect(callback)
            primary.addWidget(button)
        right.addWidget(
            CollapsibleSection(
                _TEXT[self.language]["primary_actions"],
                primary_widget,
                expanded=True,
                tooltip=_TEXT[self.language]["primary_actions"],
            )
        )

        advanced_widget = QWidget()
        advanced = QVBoxLayout(advanced_widget)
        advanced.setContentsMargins(6, 4, 6, 4)
        for caption, callback in (
            (_TEXT[self.language]["columns"], self._edit_columns),
            (_TEXT[self.language]["mapping"], self._edit_mapping),
            (_TEXT[self.language]["page"], self._edit_page),
            (_TEXT[self.language]["symbols"], self._edit_symbols),
            (_TEXT[self.language]["project_images"], self._edit_project_assets),
        ):
            button = QPushButton(caption)
            button.setToolTip(caption)
            button.clicked.connect(callback)
            advanced.addWidget(button)
        right.addWidget(
            CollapsibleSection(
                _TEXT[self.language]["advanced_actions"],
                advanced_widget,
                expanded=False,
                tooltip=_TEXT[self.language]["advanced_actions"],
            )
        )

        manager_button = QPushButton(self.localizer.text("masterlog_templates.action"))
        manager_button.setToolTip(self.localizer.text("masterlog_templates.action"))
        manager_button.clicked.connect(self._open_template_manager)
        right.addWidget(manager_button)
        refresh_button = QPushButton(_TEXT[self.language]["refresh"])
        refresh_button.setToolTip(_TEXT[self.language]["refresh"])
        refresh_button.clicked.connect(self.refresh_templates)
        right.addWidget(refresh_button)
        root.addWidget(right_widget, 4)
        return page

    def _build_assets_tab(self) -> QWidget:
        page = QWidget()
        root = QVBoxLayout(page)
        controls = QHBoxLayout()
        self.asset_search = QLineEdit()
        self.asset_search.setPlaceholderText(_TEXT[self.language]["search"])
        self.asset_search.textChanged.connect(self._filter_assets)
        controls.addWidget(self.asset_search, 1)
        self.asset_kind = QComboBox()
        self.asset_kind.addItem(_TEXT[self.language]["all"], None)
        self.asset_kind.addItem(_TEXT[self.language]["lithology"], "lithology_pattern")
        self.asset_kind.addItem(_TEXT[self.language]["depth_symbols"], "depth_symbol")
        self.asset_kind.currentIndexChanged.connect(self._filter_assets)
        controls.addWidget(self.asset_kind)
        root.addLayout(controls)

        self.asset_list = QListWidget()
        self.asset_list.setViewMode(QListWidget.ViewMode.IconMode)
        self.asset_list.setIconSize(QSize(72, 72))
        self.asset_list.setResizeMode(QListWidget.ResizeMode.Adjust)
        self.asset_list.setSelectionMode(QListWidget.SelectionMode.ExtendedSelection)
        self.asset_list.setSpacing(8)
        self.asset_list.itemDoubleClicked.connect(lambda *_: self._install_selected_assets())
        root.addWidget(self.asset_list, 1)
        self.asset_count = QLabel()
        root.addWidget(self.asset_count)
        actions = QHBoxLayout()
        selected_button = QPushButton(_TEXT[self.language]["install_selected"])
        selected_button.clicked.connect(self._install_selected_assets)
        visible_button = QPushButton(_TEXT[self.language]["install_visible"])
        visible_button.clicked.connect(self._install_visible_assets)
        actions.addWidget(selected_button)
        actions.addWidget(visible_button)
        actions.addStretch(1)
        root.addLayout(actions)
        return page

    def _build_preflight_tab(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)
        run = QPushButton(_TEXT[self.language]["preflight_run"])
        run.clicked.connect(self._run_preflight)
        layout.addWidget(run)
        self.preflight_output = QTextEdit()
        self.preflight_output.setReadOnly(True)
        layout.addWidget(self.preflight_output, 1)
        return page

    def _populate_preset_gallery(self) -> None:
        if not hasattr(self, "preset_list"):
            return
        self.preset_list.clear()
        for preset in BUILTIN_MASTERLOG_FORM_PRESETS:
            item = QListWidgetItem(preset.name(self.language))
            item.setData(Qt.ItemDataRole.UserRole, preset.preset_id)
            item.setToolTip(preset.description(self.language))
            self.preset_list.addItem(item)
        preferred = self.preset_list.findItems(
            "Геолого-технологические исследования — готовый бланк",
            Qt.MatchFlag.MatchContains,
        )
        if preferred:
            self.preset_list.setCurrentItem(preferred[0])
        elif self.preset_list.count():
            self.preset_list.setCurrentRow(0)

    def _selected_preset(self):
        item = self.preset_list.currentItem() if hasattr(self, "preset_list") else None
        preset_id = item.data(Qt.ItemDataRole.UserRole) if item is not None else None
        return next(
            (
                preset
                for preset in BUILTIN_MASTERLOG_FORM_PRESETS
                if preset.preset_id == preset_id
            ),
            None,
        )

    def _update_preset_summary(self) -> None:
        preset = self._selected_preset()
        if preset is None or not hasattr(self, "template_summary"):
            return
        if self.template_list.currentItem() is not None:
            self.template_list.blockSignals(True)
            self.template_list.clearSelection()
            self.template_list.setCurrentItem(None)
            self.template_list.blockSignals(False)
        template = preset.template
        width = sum(column.width_mm for column in template.columns)
        self.template_summary.setPlainText(
            f"{preset.name(self.language)}\n\n"
            f"{preset.description(self.language)}\n\n"
            f"{template.page_format} / {template.properties.get('orientation', 'portrait')}\n"
            f"1:{template.depth_scale}\n"
            f"{len(template.header_elements)} header elements\n"
            f"{len(template.columns)} columns / {width:g} mm"
        )

    def _create_from_selected_preset(self) -> None:
        preset = self._selected_preset()
        if preset is None:
            QMessageBox.information(
                self, self.windowTitle(), _TEXT[self.language]["select_template"]
            )
            return
        suggested = preset.name(self.language)
        name, accepted = QInputDialog.getText(
            self,
            _TEXT[self.language]["create_from_preset"],
            self.localizer.text("masterlog_templates.name"),
            text=suggested,
        )
        if not accepted or not name.strip():
            return
        try:
            template = self.controller.create_from_preset(preset.preset_id, name.strip())
        except (KeyError, RuntimeError, ValueError) as exc:
            QMessageBox.warning(self, self.windowTitle(), str(exc))
            return
        self.refresh_templates(template.template_id)
        QMessageBox.information(
            self,
            self.windowTitle(),
            {
                AppLanguage.RU: "Создана редактируемая пользовательская копия. Теперь можно открыть редактор шапки.",
                AppLanguage.KK: "Өңделетін пайдаланушы көшірмесі жасалды. Енді тақырып редакторын ашуға болады.",
                AppLanguage.EN: "An editable user copy was created. You can now open the header editor.",
            }[self.language],
        )

    def refresh_templates(self, selected_id: str | None = None) -> None:
        selected = selected_id or self._selected_template_id()
        self.template_list.clear()
        templates = sorted(
            self.controller.session.project.masterlog_templates.values(),
            key=lambda item: item.name.casefold(),
        )
        selected_item: QListWidgetItem | None = None
        for template in templates:
            item = QListWidgetItem(f"{template.name} · v{template.version}")
            item.setData(Qt.ItemDataRole.UserRole, template.template_id)
            self.template_list.addItem(item)
            if template.template_id == selected:
                selected_item = item
        if selected_item is not None:
            self.template_list.setCurrentItem(selected_item)
        elif self.template_list.count():
            self.template_list.setCurrentRow(0)
        self._update_template_summary()

    def _selected_template_id(self) -> str | None:
        item = getattr(self, "template_list", None)
        current = item.currentItem() if item is not None else None
        value = current.data(Qt.ItemDataRole.UserRole) if current is not None else None
        return str(value) if isinstance(value, str) else None

    def _selected_template(self):
        template_id = self._selected_template_id()
        return (
            self.controller.session.project.masterlog_templates.get(template_id)
            if template_id is not None
            else None
        )

    def _require_template_id(self) -> str | None:
        template_id = self._selected_template_id()
        if template_id is None:
            QMessageBox.information(self, self.windowTitle(), _TEXT[self.language]["select_template"])
        return template_id

    def _update_template_summary(self) -> None:
        template = self._selected_template()
        if template is not None and hasattr(self, "preset_list"):
            self.preset_list.blockSignals(True)
            self.preset_list.clearSelection()
            self.preset_list.setCurrentItem(None)
            self.preset_list.blockSignals(False)
        if template is None:
            self.template_summary.setPlainText(_TEXT[self.language]["no_template"])
            return
        orientation = str(template.properties.get("orientation", "portrait"))
        width = sum(column.width_mm for column in template.columns)
        self.template_summary.setPlainText(
            f"{template.name}\n\n"
            f"Format: {template.page_format} / {orientation}\n"
            f"Depth scale: 1:{template.depth_scale}\n"
            f"Header: {template.header_height_mm:g} mm\n"
            f"Header elements: {len(template.header_elements)}\n"
            f"Columns: {len(template.columns)}\n"
            f"Form width: {width:g} mm\n"
            f"Project images: {len(self.controller.session.image_assets)}\n"
            f"Project lithotypes: {len(self.controller.session.project.lithotypes)}"
        )

    def _open_form_manager(self) -> None:
        if self.open_form_manager_callback is not None:
            self.open_form_manager_callback()

    def _open_template_manager(self) -> None:
        if self.open_template_manager_callback is not None:
            self.open_template_manager_callback()
            self.refresh_templates()

    def _edit_header(self) -> None:
        template_id = self._require_template_id()
        if template_id is None:
            return
        MasterlogHeaderDialog(
            self.controller, template_id, self, language=self.language
        ).exec()
        self.refresh_templates()

    def _edit_columns(self) -> None:
        template_id = self._require_template_id()
        if template_id is None:
            return
        MasterlogColumnsDialog(
            self.controller, template_id, self, language=self.language
        ).exec()
        self.refresh_templates()

    def _edit_mapping(self) -> None:
        template_id = self._require_template_id()
        dataset = self.controller.session.current_dataset
        if template_id is None:
            return
        if dataset is None:
            QMessageBox.information(self, self.windowTitle(), self.localizer.text("formula.select_dataset"))
            return
        MasterlogCurveMappingDialog(
            self.controller, template_id, dataset, self, language=self.language
        ).exec()

    def _edit_page(self) -> None:
        template_id = self._require_template_id()
        if template_id is None:
            return
        template = self.controller.session.project.masterlog_templates[template_id]
        dialog = MasterlogPageDialog(template, self, language=self.language)
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return
        page_format, orientation, scale, header, width, height = dialog.values()
        try:
            self.controller.configure_page(
                template_id,
                page_format=page_format,
                orientation=orientation,
                depth_scale=scale,
                header_height_mm=header,
                custom_width_mm=width,
                custom_height_mm=height,
            )
        except ValueError as exc:
            QMessageBox.warning(self, self.windowTitle(), str(exc))
        self.refresh_templates()

    def _edit_symbols(self) -> None:
        template_id = self._require_template_id()
        if template_id is None:
            return
        if self.controller.session.current_well is None:
            QMessageBox.information(self, self.windowTitle(), _TEXT[self.language]["preflight_no_data"])
            return
        MasterlogSymbolsDialog(
            MasterlogSymbolController(self.controller.session),
            template_id,
            self,
            language=self.language,
        ).exec()

    def _edit_project_assets(self) -> None:
        MasterlogAssetsDialog(self.controller, self, language=self.language).exec()
        self._update_template_summary()

    def _preview(self) -> None:
        template = self._selected_template()
        depth_range = masterlog_depth_range(self.controller.session)
        if template is None:
            self._require_template_id()
            return
        if depth_range is None:
            QMessageBox.information(self, self.windowTitle(), _TEXT[self.language]["preflight_no_data"])
            return
        settings = MasterlogOutputSettings(depth_range[0], depth_range[1], language=self.language)
        MasterlogPreviewDialog(
            template,
            self.controller.session,
            self,
            language=self.language,
            settings=settings,
        ).exec()

    def _filter_assets(self) -> None:
        kind = self.asset_kind.currentData() if hasattr(self, "asset_kind") else None
        query = self.asset_search.text() if hasattr(self, "asset_search") else ""
        self._visible_assets = self.registry.search(
            query,
            kind=str(kind) if isinstance(kind, str) else None,
            language=self.language.value,
        )
        self.asset_list.clear()
        for asset in self._visible_assets:
            item = QListWidgetItem(asset.display_name(self.language.value))
            item.setData(Qt.ItemDataRole.UserRole, asset.asset_id)
            thumbnail = asset.thumbnail_path or asset.asset_path
            pixmap = QPixmap(str(thumbnail))
            if not pixmap.isNull():
                item.setIcon(QIcon(pixmap))
            item.setToolTip(
                f"{asset.asset_id}\n{asset.category}\n" + ", ".join(asset.aliases[:8])
            )
            self.asset_list.addItem(item)
        self.asset_count.setText(
            _TEXT[self.language]["asset_count"].format(
                shown=len(self._visible_assets), total=len(self.registry)
            )
        )

    def _selected_assets(self) -> tuple[AssetDefinition, ...]:
        ids = {
            str(item.data(Qt.ItemDataRole.UserRole))
            for item in self.asset_list.selectedItems()
        }
        return tuple(asset for asset in self._visible_assets if asset.asset_id in ids)

    def _install_selected_assets(self) -> None:
        assets = self._selected_assets()
        if assets:
            self._install_assets(assets)

    def _install_visible_assets(self) -> None:
        if self._visible_assets:
            self._install_assets(self._visible_assets)

    def _install_assets(self, assets: tuple[AssetDefinition, ...]) -> None:
        try:
            images, lithotypes = install_assets_into_project(self.controller.session, assets)
        except (OSError, RuntimeError, ValueError) as exc:
            QMessageBox.warning(self, self.windowTitle(), str(exc))
            return
        QMessageBox.information(
            self,
            self.windowTitle(),
            _TEXT[self.language]["installed"].format(images=images, lithotypes=lithotypes),
        )
        self._update_template_summary()

    def _run_preflight(self) -> None:
        template = self._selected_template()
        depth_range = masterlog_depth_range(self.controller.session)
        if template is None:
            self.preflight_output.setPlainText(_TEXT[self.language]["select_template"])
            return
        if depth_range is None:
            self.preflight_output.setPlainText(_TEXT[self.language]["preflight_no_data"])
            return
        settings = MasterlogOutputSettings(depth_range[0], depth_range[1], language=self.language)
        report = analyze_masterlog_output(template, self.controller.session, settings)
        pages_text = self.localizer.text(
            "masterlog_preflight.pages", pages=report.page_count
        )
        if not report.issues:
            self.preflight_output.setPlainText(
                _TEXT[self.language]["preflight_ok"] + f"\n{pages_text}"
            )
            return
        severity_labels = {
            "error": {
                AppLanguage.RU: "ОШИБКА",
                AppLanguage.KK: "ҚАТЕ",
                AppLanguage.EN: "ERROR",
            }[self.language],
            "warning": {
                AppLanguage.RU: "ПРЕДУПРЕЖДЕНИЕ",
                AppLanguage.KK: "ЕСКЕРТУ",
                AppLanguage.EN: "WARNING",
            }[self.language],
        }
        lines = [pages_text]
        for issue in report.issues:
            values = dict(issue.values)
            message = self.localizer.text(
                f"masterlog_preflight.{issue.code}", **values
            )
            severity = severity_labels.get(issue.severity.value, issue.severity.value.upper())
            lines.append(f"[{severity}] {message}")
        self.preflight_output.setPlainText("\n".join(lines))
