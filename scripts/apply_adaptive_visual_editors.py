from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def read(path: str) -> str:
    return (ROOT / path).read_text(encoding="utf-8")


def write(path: str, text: str) -> None:
    (ROOT / path).write_text(text, encoding="utf-8")


def replace_once(text: str, old: str, new: str, label: str) -> str:
    count = text.count(old)
    if count != 1:
        raise RuntimeError(f"{label}: expected one occurrence, found {count}")
    return text.replace(old, new, 1)


def sub_once(text: str, pattern: str, replacement: str, label: str) -> str:
    updated, count = re.subn(pattern, replacement, text, count=1, flags=re.S)
    if count != 1:
        raise RuntimeError(f"{label}: expected one regex occurrence, found {count}")
    return updated


def patch_header_editor() -> None:
    path = "src/geoworkbench/ui/masterlog_header_dialog.py"
    text = read(path)
    text = replace_once(
        text,
        "import json\nfrom pathlib import Path",
        "import json\nfrom copy import deepcopy\nfrom pathlib import Path",
        "header deepcopy import",
    )
    text = replace_once(
        text,
        "from PySide6.QtCore import QRectF, Qt",
        "from PySide6.QtCore import QRectF, QSettings, Qt, QTimer",
        "header QtCore imports",
    )
    text = replace_once(
        text,
        "    QSplitter,\n    QTextEdit,",
        "    QSplitter,\n    QStyle,\n    QTextEdit,",
        "header style import",
    )
    text = replace_once(
        text,
        "from geoworkbench.domain.models import MasterlogHeaderElement",
        "from geoworkbench.domain.models import MasterlogHeaderElement, MasterlogTemplate",
        "header model import",
    )
    text = replace_once(
        text,
        "from geoworkbench.project.masterlog_template_controller import MasterlogTemplateController",
        "from geoworkbench.project.masterlog_template_controller import MasterlogTemplateController\nfrom geoworkbench.project.session import ProjectSession",
        "header session import",
    )
    text = replace_once(
        text,
        "from geoworkbench.ui.header_preview_widget import HeaderPreviewWidget",
        "from geoworkbench.ui.header_preview_widget import HeaderPreviewWidget\nfrom geoworkbench.ui.adaptive_toolbar import AdaptiveActionToolBar",
        "header adaptive toolbar import",
    )

    text = replace_once(
        text,
        "        logo_catalog_controller: LogoCatalogController | None = None,\n    ) -> None:",
        "        logo_catalog_controller: LogoCatalogController | None = None,\n"
        "        preview_template: MasterlogTemplate | None = None,\n"
        "        preview_session: ProjectSession | None = None,\n"
        "        preview_element_id: str | None = None,\n"
        "    ) -> None:",
        "header element signature",
    )
    text = replace_once(
        text,
        "        self.imported_assets: dict[str, ImageAsset] = {}\n        self.setWindowTitle",
        "        self.imported_assets: dict[str, ImageAsset] = {}\n"
        "        self.preview_template = preview_template\n"
        "        self.preview_session = preview_session\n"
        "        self.preview_element_id = preview_element_id\n"
        "        self.live_preview: HeaderPreviewWidget | None = None\n"
        "        self.setWindowTitle",
        "header element preview attrs",
    )
    text = replace_once(
        text,
        "        layout = QFormLayout(self)",
        "        form_widget = QWidget()\n        layout = QFormLayout(form_widget)",
        "header element form widget",
    )
    text = replace_once(
        text,
        "        self.legend_scope_input.currentIndexChanged.connect(self._update_legend_manual_visibility)\n"
        "        self._update_property_inputs(str(self.type_input.currentData() or \"text\"))",
        "        self.legend_scope_input.currentIndexChanged.connect(self._update_legend_manual_visibility)\n"
        "        self._update_property_inputs(str(self.type_input.currentData() or \"text\"))\n\n"
        "        form_scroll = QScrollArea()\n"
        "        form_scroll.setWidgetResizable(True)\n"
        "        form_scroll.setWidget(form_widget)\n"
        "        root = QHBoxLayout(self)\n"
        "        root.addWidget(form_scroll, 3)\n"
        "        if self.preview_template is not None and self.preview_session is not None:\n"
        "            preview_panel = QGroupBox(\n"
        "                {\n"
        "                    AppLanguage.RU: \"Живой предпросмотр\",\n"
        "                    AppLanguage.KK: \"Тікелей алдын ала қарау\",\n"
        "                    AppLanguage.EN: \"Live preview\",\n"
        "                }[language]\n"
        "            )\n"
        "            preview_layout = QVBoxLayout(preview_panel)\n"
        "            preview_hint = QLabel(\n"
        "                {\n"
        "                    AppLanguage.RU: \"Любое изменение поля сразу отображается здесь до сохранения.\",\n"
        "                    AppLanguage.KK: \"Өрістің әр өзгерісі сақтауға дейін осында көрінеді.\",\n"
        "                    AppLanguage.EN: \"Every control change is shown here before saving.\",\n"
        "                }[language]\n"
        "            )\n"
        "            preview_hint.setWordWrap(True)\n"
        "            preview_layout.addWidget(preview_hint)\n"
        "            self.live_preview = HeaderPreviewWidget(\n"
        "                self.preview_session, preview_panel, language=language\n"
        "            )\n"
        "            self.live_preview.setMinimumSize(460, 420)\n"
        "            preview_layout.addWidget(self.live_preview, 1)\n"
        "            root.addWidget(preview_panel, 4)\n"
        "            self.setMinimumSize(980, 650)\n"
        "            self.resize(1320, 780)\n"
        "            self._connect_live_preview()\n"
        "            QTimer.singleShot(0, self._refresh_live_preview)\n"
        "        else:\n"
        "            self.setMinimumSize(560, 600)",
        "header element live preview layout",
    )
    marker = "    def _update_property_inputs(self, element_type: str) -> None:\n"
    live_methods = '''    def _connect_live_preview(self) -> None:\n        controls = (\n            self.type_input,\n            *self.inputs,\n            self.text_input,\n            self.field_input,\n            self.text_color_input,\n            self.font_size_input,\n            self.bold_input,\n            self.alignment_input,\n            self.text_orientation_input,\n            self.text_position_input,\n            self.frame_input,\n            self.background_input,\n            self.image_input,\n            self.image_mode_input,\n            self.image_rotation_input,\n            self.image_opacity_input,\n            self.line_color_input,\n            self.line_width_input,\n            self.legend_scope_input,\n            self.legend_columns_input,\n            self.legend_code_input,\n            self.lithotype_input,\n            self.lithotype_label_mode_input,\n        )\n        for control in controls:\n            if isinstance(control, QLineEdit):\n                control.textChanged.connect(self._refresh_live_preview)\n            elif isinstance(control, QComboBox):\n                control.currentIndexChanged.connect(self._refresh_live_preview)\n            elif isinstance(control, (QDoubleSpinBox, QSpinBox)):\n                control.valueChanged.connect(self._refresh_live_preview)\n            elif isinstance(control, QCheckBox):\n                control.toggled.connect(self._refresh_live_preview)\n        self.legend_manual_input.itemSelectionChanged.connect(self._refresh_live_preview)\n\n    def _refresh_live_preview(self, *_args) -> None:\n        if (\n            self.live_preview is None\n            or self.preview_template is None\n            or self.preview_session is None\n        ):\n            return\n        try:\n            kind, x, y, width, height, properties = self.values()\n        except (ValueError, json.JSONDecodeError):\n            return\n        template = deepcopy(self.preview_template)\n        element_id = self.preview_element_id or \"__live_preview_element__\"\n        candidate = MasterlogHeaderElement(\n            element_id, kind, x, y, width, height, properties\n        )\n        for index, item in enumerate(template.header_elements):\n            if item.element_id == element_id:\n                template.header_elements[index] = candidate\n                break\n        else:\n            template.header_elements.append(candidate)\n        template.header_height_mm = max(\n            template.header_height_mm, y + height + 2.0\n        )\n        self.live_preview.set_template(template)\n\n'''
    text = replace_once(text, marker, live_methods + marker, "header element live preview methods")

    text = replace_once(
        text,
        "        self.setMinimumSize(720, 480)\n        self.resize(1120, 700)",
        "        self.setMinimumSize(900, 600)\n        self.resize(1500, 900)",
        "header editor geometry",
    )
    text = sub_once(
        text,
        r"\n        settings = QHBoxLayout\(\).*?        settings\.addStretch\(1\)\n",
        "\n",
        "header remove fixed settings row",
    )
    text = replace_once(
        text,
        "        left_buttons = QHBoxLayout()\n"
        "        left_buttons.addWidget(self.data_button)\n"
        "        left_buttons.addWidget(self.catalog_button)\n"
        "        left_buttons.addWidget(self.save_catalog_button)\n"
        "        left_buttons.addWidget(self.preset_button)\n"
        "        left_buttons.addWidget(self.edit_zoom_button)\n"
        "        left_buttons.addWidget(self.fit_button)\n",
        "        self.toolbar = AdaptiveActionToolBar(parent=self)\n"
        "        for button in (\n"
        "            self.data_button,\n"
        "            self.catalog_button,\n"
        "            self.save_catalog_button,\n"
        "            self.preset_button,\n"
        "            self.edit_zoom_button,\n"
        "            self.fit_button,\n"
        "        ):\n"
        "            self.toolbar.addWidget(button)\n",
        "header main toolbar",
    )
    text = replace_once(
        text,
        "        element_buttons = QHBoxLayout()",
        "        self.element_toolbar = AdaptiveActionToolBar(parent=self)",
        "header element toolbar init",
    )
    text = replace_once(
        text,
        "            element_buttons.addWidget(button)",
        "            self.element_toolbar.addWidget(button)",
        "header element toolbar buttons",
    )
    text = replace_once(
        text,
        "        left_layout.addLayout(left_buttons)\n"
        "        left_layout.addWidget(self.list, 1)\n"
        "        left_layout.addLayout(element_buttons)",
        "        left_layout.addWidget(self.element_toolbar)\n"
        "        left_layout.addWidget(self.list, 1)",
        "header left adaptive layout",
    )
    old_right = '''        right = QWidget()\n        right_layout = QVBoxLayout(right)\n        right_layout.setContentsMargins(0, 0, 0, 0)\n        right_layout.addWidget(hint)\n        right_layout.addWidget(self.page_info_label)\n        right_layout.addWidget(QLabel({AppLanguage.RU: "Обзор всей шапки (всегда видна целиком)", AppLanguage.KK: "Тақырыптың толық шолуы", AppLanguage.EN: "Whole-header overview"}[language]))\n        right_layout.addWidget(self.overview, 1)\n        right_layout.addWidget(QLabel({AppLanguage.RU: "Рабочий холст: перетаскивание, прокрутка и точная правка", AppLanguage.KK: "Жұмыс кенебі: жылжыту, айналдыру және дәл өңдеу", AppLanguage.EN: "Editing canvas: drag, scroll and precise adjustment"}[language]))\n        right_layout.addWidget(self.preview, 2)\n'''
    new_right = '''        right = QWidget()\n        right_layout = QVBoxLayout(right)\n        right_layout.setContentsMargins(0, 0, 0, 0)\n        right_layout.addWidget(hint)\n        right_layout.addWidget(self.page_info_label)\n        overview_group = QGroupBox(\n            {AppLanguage.RU: "Обзор всей шапки", AppLanguage.KK: "Тақырыптың толық шолуы", AppLanguage.EN: "Whole-header overview"}[language]\n        )\n        overview_layout = QVBoxLayout(overview_group)\n        overview_layout.addWidget(self.overview)\n        workspace_group = QGroupBox(\n            {AppLanguage.RU: "Рабочий холст", AppLanguage.KK: "Жұмыс кенебі", AppLanguage.EN: "Editing canvas"}[language]\n        )\n        workspace_layout = QVBoxLayout(workspace_group)\n        workspace_layout.addWidget(self.preview)\n        self.preview_splitter = QSplitter(Qt.Orientation.Vertical)\n        self.preview_splitter.setChildrenCollapsible(False)\n        self.preview_splitter.addWidget(overview_group)\n        self.preview_splitter.addWidget(workspace_group)\n        self.preview_splitter.setStretchFactor(0, 0)\n        self.preview_splitter.setStretchFactor(1, 1)\n        right_layout.addWidget(self.preview_splitter, 1)\n'''
    text = replace_once(text, old_right, new_right, "header vertical preview splitter")
    text = replace_once(
        text,
        "        inspector_form = QFormLayout()\n        self.geometry_inputs",
        "        inspector_form = QFormLayout()\n"
        "        inspector_form.addRow(_TEXT[language][\"height\"], self.height_input)\n"
        "        inspector_form.addRow(_TEXT[language][\"snap\"], self.snap_checkbox)\n"
        "        inspector_form.addRow(_TEXT[language][\"grid\"], self.snap_input)\n"
        "        self.geometry_inputs",
        "header move settings to inspector",
    )
    text = replace_once(
        text,
        "        splitter = QSplitter(Qt.Orientation.Horizontal)\n"
        "        splitter.addWidget(left)\n"
        "        splitter.addWidget(right)\n"
        "        splitter.addWidget(inspector)\n"
        "        splitter.setStretchFactor(0, 0)\n"
        "        splitter.setStretchFactor(1, 1)\n"
        "        splitter.setStretchFactor(2, 0)\n"
        "        splitter.setSizes([300, 850, 300])",
        "        inspector_scroll = QScrollArea()\n"
        "        inspector_scroll.setWidgetResizable(True)\n"
        "        inspector_scroll.setWidget(inspector)\n"
        "        inspector_scroll.setMinimumWidth(250)\n"
        "        self.main_splitter = QSplitter(Qt.Orientation.Horizontal)\n"
        "        self.main_splitter.setChildrenCollapsible(False)\n"
        "        self.main_splitter.addWidget(left)\n"
        "        self.main_splitter.addWidget(right)\n"
        "        self.main_splitter.addWidget(inspector_scroll)\n"
        "        self.main_splitter.setStretchFactor(0, 0)\n"
        "        self.main_splitter.setStretchFactor(1, 1)\n"
        "        self.main_splitter.setStretchFactor(2, 0)\n"
        "        settings_store = QSettings()\n"
        "        main_state = settings_store.value(\"ui/masterlog_header/main_splitter\")\n"
        "        preview_state = settings_store.value(\"ui/masterlog_header/preview_splitter\")\n"
        "        if main_state is not None:\n"
        "            self.main_splitter.restoreState(main_state)\n"
        "        else:\n"
        "            self.main_splitter.setSizes([300, 900, 300])\n"
        "        if preview_state is not None:\n"
        "            self.preview_splitter.restoreState(preview_state)\n"
        "        else:\n"
        "            self.preview_splitter.setSizes([260, 520])",
        "header adaptive splitter",
    )
    text = replace_once(
        text,
        "        layout = QVBoxLayout(self)\n"
        "        layout.addLayout(settings)\n"
        "        layout.addWidget(splitter, 1)",
        "        layout = QVBoxLayout(self)\n"
        "        layout.addWidget(self.toolbar)\n"
        "        layout.addWidget(self.main_splitter, 1)",
        "header root toolbar",
    )
    property_marker = "    @property\n    def template(self):\n"
    state_methods = '''    def _save_ui_state(self) -> None:\n        settings = QSettings()\n        settings.setValue(\"ui/masterlog_header/main_splitter\", self.main_splitter.saveState())\n        settings.setValue(\"ui/masterlog_header/preview_splitter\", self.preview_splitter.saveState())\n\n    def accept(self) -> None:\n        self._save_ui_state()\n        super().accept()\n\n    def reject(self) -> None:\n        self._save_ui_state()\n        super().reject()\n\n'''
    text = replace_once(text, property_marker, state_methods + property_marker, "header UI state methods")

    old_add = '''        dialog = HeaderElementDialog(\n            self,\n            language=self.localizer.language,\n            image_assets=self.controller.session.image_assets,\n            lithotypes=self._available_lithotypes(),\n            logo_catalog_controller=LogoCatalogController(self.controller.session),\n        )'''
    new_add = '''        dialog = HeaderElementDialog(\n            self,\n            language=self.localizer.language,\n            image_assets=self.controller.session.image_assets,\n            lithotypes=self._available_lithotypes(),\n            logo_catalog_controller=LogoCatalogController(self.controller.session),\n            preview_template=self.template,\n            preview_session=self.controller.session,\n            preview_element_id=None,\n        )'''
    text = replace_once(text, old_add, new_add, "header add live preview")
    old_edit = '''            dialog = HeaderElementDialog(\n                self,\n                element=element,\n                language=self.localizer.language,\n                image_assets=self.controller.session.image_assets,\n                lithotypes=self._available_lithotypes(),\n                logo_catalog_controller=LogoCatalogController(self.controller.session),\n            )'''
    new_edit = '''            dialog = HeaderElementDialog(\n                self,\n                element=element,\n                language=self.localizer.language,\n                image_assets=self.controller.session.image_assets,\n                lithotypes=self._available_lithotypes(),\n                logo_catalog_controller=LogoCatalogController(self.controller.session),\n                preview_template=self.template,\n                preview_session=self.controller.session,\n                preview_element_id=element.element_id,\n            )'''
    text = replace_once(text, old_edit, new_edit, "header edit live preview")
    write(path, text)


def patch_constructor() -> None:
    path = "src/geoworkbench/ui/constructor_dialog.py"
    text = read(path)
    text = replace_once(
        text,
        "    QPushButton,\n    QSplitter,",
        "    QPushButton,\n    QSplitter,\n    QStyle,",
        "constructor QStyle import",
    )
    text = replace_once(
        text,
        "from geoworkbench.ui.collapsible_section import CollapsibleSection",
        "from geoworkbench.ui.collapsible_section import CollapsibleSection\n"
        "from geoworkbench.ui.header_preview_widget import HeaderPreviewWidget\n"
        "from geoworkbench.ui.adaptive_toolbar import AdaptiveActionToolBar",
        "constructor preview imports",
    )
    text = replace_once(
        text,
        "        self.template_summary = QTextEdit()\n"
        "        self.template_summary.setReadOnly(True)\n"
        "        self.template_summary.setToolTip(\n"
        "            _TEXT[self.language][\"select_template\"]\n"
        "        )\n"
        "        right.addWidget(self.template_summary, 1)",
        "        preview_title = QLabel(\n"
        "            {\n"
        "                AppLanguage.RU: \"Визуальный контроль выбранной формы\",\n"
        "                AppLanguage.KK: \"Таңдалған пішінді визуалды бақылау\",\n"
        "                AppLanguage.EN: \"Visual control of the selected form\",\n"
        "            }[self.language]\n"
        "        )\n"
        "        preview_title.setStyleSheet(\"font-weight:700; color:#0f172a;\")\n"
        "        right.addWidget(preview_title)\n"
        "        self.constructor_preview = HeaderPreviewWidget(\n"
        "            self.controller.session, right_widget, language=self.language\n"
        "        )\n"
        "        self.constructor_preview.setMinimumHeight(360)\n"
        "        right.addWidget(self.constructor_preview, 2)\n"
        "        self.template_summary = QTextEdit()\n"
        "        self.template_summary.setReadOnly(True)\n"
        "        self.template_summary.setMaximumHeight(150)\n"
        "        self.template_summary.setToolTip(\n"
        "            _TEXT[self.language][\"select_template\"]\n"
        "        )\n"
        "        right.addWidget(self.template_summary)",
        "constructor visual preview",
    )
    text = sub_once(
        text,
        r"        primary_widget = QWidget\(\).*?        right\.addWidget\(\n            CollapsibleSection\(\n                _TEXT\[self\.language\]\[\"advanced_actions\"\],.*?        \)\n",
        "        self.print_toolbar = AdaptiveActionToolBar(parent=right_widget)\n"
        "        for caption, callback, icon in (\n"
        "            (_TEXT[self.language][\"header\"], self._edit_header, QStyle.StandardPixmap.SP_FileDialogDetailedView),\n"
        "            (_TEXT[self.language][\"preview\"], self._preview, QStyle.StandardPixmap.SP_FileDialogContentsView),\n"
        "            (_TEXT[self.language][\"columns\"], self._edit_columns, QStyle.StandardPixmap.SP_FileDialogListView),\n"
        "            (_TEXT[self.language][\"mapping\"], self._edit_mapping, QStyle.StandardPixmap.SP_BrowserReload),\n"
        "            (_TEXT[self.language][\"page\"], self._edit_page, QStyle.StandardPixmap.SP_FileDialogInfoView),\n"
        "            (_TEXT[self.language][\"symbols\"], self._edit_symbols, QStyle.StandardPixmap.SP_DirIcon),\n"
        "            (_TEXT[self.language][\"project_images\"], self._edit_project_assets, QStyle.StandardPixmap.SP_FileIcon),\n"
        "        ):\n"
        "            self.print_toolbar.add_standard_action(caption, callback, icon=icon)\n"
        "        right.addWidget(self.print_toolbar)\n",
        "constructor adaptive print toolbar",
    )
    text = replace_once(
        text,
        "        template = preset.template\n        width = sum(column.width_mm for column in template.columns)",
        "        template = preset.template\n"
        "        self.constructor_preview.set_template(template)\n"
        "        width = sum(column.width_mm for column in template.columns)",
        "constructor preset preview",
    )
    text = replace_once(
        text,
        "        if template is None:\n"
        "            self.template_summary.setPlainText(_TEXT[self.language][\"no_template\"])\n"
        "            return\n"
        "        orientation = str(template.properties.get(\"orientation\", \"portrait\"))",
        "        if template is None:\n"
        "            self.template_summary.setPlainText(_TEXT[self.language][\"no_template\"])\n"
        "            self.constructor_preview.set_template(None)\n"
        "            return\n"
        "        self.constructor_preview.set_template(template)\n"
        "        orientation = str(template.properties.get(\"orientation\", \"portrait\"))",
        "constructor template preview",
    )
    write(path, text)


def patch_skf_import() -> None:
    path = "src/geoworkbench/ui/main_window.py"
    text = read(path)
    text = replace_once(
        text,
        "from geoworkbench.ui.logo_catalog_dialog import LogoCatalogDialog",
        "from geoworkbench.ui.logo_catalog_dialog import LogoCatalogDialog\n"
        "from geoworkbench.ui.skf_import_options_dialog import (\n"
        "    SkfImportMode,\n"
        "    SkfImportOptionsDialog,\n"
        ")",
        "main SKF mode imports",
    )
    text = replace_once(
        text,
        "        try:\n"
        "            _form, summary = self._import_skf_form_and_header(Path(filename))",
        "        options = SkfImportOptionsDialog(self, language=self.language)\n"
        "        if options.exec() != QDialog.DialogCode.Accepted:\n"
        "            return False\n"
        "        try:\n"
        "            _form, summary = self._import_skf_form_and_header(\n"
        "                Path(filename), mode=options.mode\n"
        "            )",
        "main SKF option prompt",
    )
    old_method = '''    def _import_skf_form_and_header(self, source: Path):\n        result = import_skf_file(source)\n        existing_template_names = {\n            item.name.casefold() for item in self.session.project.masterlog_templates.values()\n        }\n        template_name = result.header_template.name\n        suffix = 2\n        while template_name.casefold() in existing_template_names:\n            template_name = f"{result.header_template.name} ({suffix})"\n            suffix += 1\n        template = self.masterlog_template_controller.import_template(\n            result.header_template, result.image_assets, template_name\n        )\n        header_name = f"{template.name} — печатная шапка"\n        header_template = self.masterlog_template_controller.save_header_to_catalog(\n            template.template_id, header_name\n        )\n        form = result.form\n        form.print_header_template_id = header_template.template_id\n        existing_form_names = {item.name.casefold() for item in self.form_repository.list_forms()}\n        original_name = form.name\n        suffix = 2\n        while form.name.casefold() in existing_form_names:\n            form.name = f"{original_name} ({suffix})"\n            suffix += 1\n        self.form_repository.save(form)\n        warning_text = ""\n        if result.report.warnings:\n            warning_text = "\\n\\nПредупреждения:\\n- " + "\\n- ".join(result.report.warnings)\n        summary = (\n            f"SKF импортирован: {result.report.source_name}\\n"\n            f"Компонентов Delphi: {result.report.component_count}\\n"\n            f"Колонок формы: {result.report.column_count}\\n"\n            f"Элементов шапки: {result.report.header_element_count}\\n"\n            f"Изображений: {result.report.image_asset_count}\\n"\n            f"Форма сохранена: {form.name}\\n"\n            f"Шаблон Masterlog сохранён: {template.name}\\n"\n            f"Печатная шапка сохранена в каталог: {header_template.name}"\n            f"{warning_text}"\n        )\n        return form, summary\n'''
    new_method = '''    def _import_skf_form_and_header(\n        self,\n        source: Path,\n        *,\n        mode: SkfImportMode = SkfImportMode.FORM_AND_HEADER,\n    ):\n        result = import_skf_file(source)\n        form = None\n        template = None\n        header_template = None\n\n        existing_template_names = {\n            item.name.casefold() for item in self.session.project.masterlog_templates.values()\n        }\n        template_name = result.header_template.name\n        suffix = 2\n        while template_name.casefold() in existing_template_names:\n            template_name = f"{result.header_template.name} ({suffix})"\n            suffix += 1\n\n        if mode is SkfImportMode.FORM_AND_HEADER:\n            template = self.masterlog_template_controller.import_template(\n                result.header_template, result.image_assets, template_name\n            )\n            header_name = f"{template.name} — печатная шапка"\n            header_template = self.masterlog_template_controller.save_header_to_catalog(\n                template.template_id, header_name\n            )\n        elif mode is SkfImportMode.HEADER_ONLY:\n            header_template = self.masterlog_template_controller.import_header_template(\n                result.header_template,\n                result.image_assets,\n                f"{template_name} — печатная шапка",\n            )\n\n        if mode in {SkfImportMode.FORM_AND_HEADER, SkfImportMode.FORM_ONLY}:\n            form = result.form\n            if header_template is not None:\n                form.print_header_template_id = header_template.template_id\n            existing_form_names = {\n                item.name.casefold() for item in self.form_repository.list_forms()\n            }\n            original_name = form.name\n            suffix = 2\n            while form.name.casefold() in existing_form_names:\n                form.name = f"{original_name} ({suffix})"\n                suffix += 1\n            self.form_repository.save(form)\n\n        warning_text = ""\n        if result.report.warnings:\n            warning_text = "\\n\\nПредупреждения:\\n- " + "\\n- ".join(\n                result.report.warnings\n            )\n        lines = [\n            f"SKF импортирован: {result.report.source_name}",\n            f"Компонентов Delphi: {result.report.component_count}",\n            f"Колонок формы: {result.report.column_count}",\n            f"Элементов шапки: {result.report.header_element_count}",\n            f"Изображений: {result.report.image_asset_count}",\n        ]\n        if form is not None:\n            lines.append(f"Форма сохранена: {form.name}")\n        if template is not None:\n            lines.append(f"Шаблон Masterlog сохранён: {template.name}")\n        if header_template is not None:\n            lines.append(\n                f"Печатная шапка сохранена в каталог: {header_template.name}"\n            )\n        summary = "\\n".join(lines) + warning_text\n        return form, summary\n'''
    text = replace_once(text, old_method, new_method, "main SKF mode implementation")
    write(path, text)


def patch_docs() -> None:
    docs_path = "docs/PRINT_HEADER_AND_LOGO_CATALOGS.md"
    docs = read(docs_path)
    addition = '''\n\n## Адаптивный визуальный редактор\n\nРедактор печатной шапки использует адаптивный тулбар: действия, которые не помещаются по ширине,\nавтоматически переходят в стандартное overflow-меню Qt. Размеры списка элементов, WYSIWYG-обзора,\nрабочего холста и инспектора сохраняются между открытиями. Панели разделены перемещаемыми\nразделителями, а инспектор прокручивается и не сжимает центральный холст.\n\nОкно «Содержимое и стиль» показывает живой WYSIWYG-предпросмотр временной копии элемента. Текст,\nцвет, шрифт, изображение, линия, легенда, координаты и размеры отображаются до нажатия ОК.\nРедактор дорожки планшета также содержит постоянный предпросмотр печатной шапки, шкал, сетки и\nдемонстрационных кривых; изменения названий, ширины, ориентации, диапазонов и стилей видны сразу.\n\nИмпорт `.skf` предлагает три явных режима: полный комплект «форма + шапка + Masterlog», только\nпланшетная форма или только повторно используемая печатная шапка.\n'''
    if "## Адаптивный визуальный редактор" not in docs:
        docs += addition
    write(docs_path, docs)

    changelog_path = "docs/CHANGELOG.md"
    changelog = read(changelog_path)
    marker = "## Unreleased\n"
    entry = (
        "\n- Редакторы шапок и планшетных дорожек стали адаптивными: тулбары с overflow-меню, "
        "сохраняемые разделители панелей, живой WYSIWYG-контроль свойств элемента и дорожки; "
        "импорт SKF получил явные режимы полного комплекта, только формы и только шапки.\n"
    )
    if entry.strip() not in changelog:
        changelog = changelog.replace(marker, marker + entry, 1)
    write(changelog_path, changelog)


if __name__ == "__main__":
    patch_header_editor()
    patch_constructor()
    patch_skf_import()
    patch_docs()
