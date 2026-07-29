from __future__ import annotations

from pathlib import Path

ROOT = Path.cwd()


def replace_once(relative: str, old: str, new: str) -> None:
    path = ROOT / relative
    text = path.read_text(encoding="utf-8")
    count = text.count(old)
    if count != 1:
        raise RuntimeError(f"{relative}: expected one match, found {count}\n--- needle ---\n{old[:500]}")
    path.write_text(text.replace(old, new, 1), encoding="utf-8")


def append_once(relative: str, marker: str, block: str) -> None:
    path = ROOT / relative
    text = path.read_text(encoding="utf-8")
    if block.strip() in text:
        return
    if marker not in text:
        raise RuntimeError(f"{relative}: marker not found: {marker}")
    path.write_text(text.replace(marker, marker + block, 1), encoding="utf-8")


replace_once(
    "src/geoworkbench/project/masterlog_template_controller.py",
    """        self._touch(template)\n        return template.header_height_mm\n\n    def duplicate_header_element(\n""",
    """        self._touch(template)\n        return template.header_height_mm\n\n    def fit_header_to_page(\n        self,\n        template_id: str,\n        page_width_mm: float,\n        *,\n        padding_mm: float = 2.0,\n    ) -> float:\n        \"\"\"Fit every header element into the printable page width as one composition.\n\n        Imported SKF headers often retain a wider vendor canvas than the selected A3/A4\n        page. The operation preserves relative geometry, scales text/line metrics and\n        expands the declared header height to the actual lower element boundary.\n        \"\"\"\n\n        template = self._require(template_id)\n        values = (page_width_mm, padding_mm)\n        if any(\n            isinstance(value, bool)\n            or not isinstance(value, (int, float))\n            or not isfinite(value)\n            for value in values\n        ):\n            raise ValueError(\"Размер страницы и поля должны быть конечными числами\")\n        page_width = float(page_width_mm)\n        padding = float(padding_mm)\n        if not 25.0 <= page_width <= 5000.0:\n            raise ValueError(\"Ширина страницы должна быть от 25 до 5000 мм\")\n        if not 0.0 <= padding <= min(50.0, page_width / 4.0):\n            raise ValueError(\"Поле подгонки выходит за допустимые границы\")\n        if not template.header_elements:\n            return 1.0\n\n        source_left = min(element.x_mm for element in template.header_elements)\n        source_right = max(\n            element.x_mm + element.width_mm for element in template.header_elements\n        )\n        source_width = max(1.0, source_right - source_left)\n        available_width = max(1.0, page_width - padding * 2.0)\n        scale = min(1.0, available_width / source_width)\n\n        metric_keys = (\"font_size_mm\", \"placeholder_font_size_mm\", \"width\")\n        fitted: list[MasterlogHeaderElement] = []\n        for element in template.header_elements:\n            properties = deepcopy(element.properties)\n            for key in metric_keys:\n                value = properties.get(key)\n                if isinstance(value, (int, float)) and not isinstance(value, bool):\n                    properties[key] = max(0.1, float(value) * scale)\n            fitted.append(\n                self._validated_header_element(\n                    element.element_id,\n                    element.element_type,\n                    padding + (element.x_mm - source_left) * scale,\n                    max(0.0, element.y_mm * scale),\n                    max(0.1, element.width_mm * scale),\n                    max(0.1, element.height_mm * scale),\n                    properties,\n                )\n            )\n\n        template.header_elements = fitted\n        lower_boundary = max(\n            element.y_mm + element.height_mm for element in template.header_elements\n        )\n        template.header_height_mm = min(500.0, max(10.0, lower_boundary + padding))\n        self._touch(template)\n        return scale\n\n    def duplicate_header_element(\n""",
)

replace_once(
    "src/geoworkbench/ui/header_catalog_dialog.py",
    """from geoworkbench.printing.header_catalog import HeaderCatalogItem\nfrom geoworkbench.services.localization import AppLanguage\n""",
    """from geoworkbench.printing.header_catalog import (\n    HeaderCatalogItem,\n    resolve_catalog_header,\n)\nfrom geoworkbench.services.localization import AppLanguage\nfrom geoworkbench.ui.header_preview_widget import (\n    HeaderPreviewDialog,\n    HeaderPreviewWidget,\n)\n""",
)
replace_once(
    "src/geoworkbench/ui/header_catalog_dialog.py",
    """        self.details = QLabel()\n        self.details.setWordWrap(True)\n        self.orientation = QComboBox()\n""",
    """        self.preview = HeaderPreviewWidget(controller.session, self, language=language)\n        self.preview.setObjectName(\"header-catalog-visual-preview\")\n        self.preview.setMinimumSize(620, 390)\n        self.details = QLabel()\n        self.details.setWordWrap(True)\n        self.orientation = QComboBox()\n""",
)
replace_once(
    "src/geoworkbench/ui/header_catalog_dialog.py",
    """        self.use_button = QPushButton(\"Использовать шапку\")\n        self.use_button.clicked.connect(self._use)\n        close_button = QPushButton(\"Закрыть\")\n""",
    """        self.preview_button = QPushButton(\"Развернуть предпросмотр...\")\n        self.preview_button.clicked.connect(self._open_preview)\n        self.use_button = QPushButton(\"Использовать шапку\")\n        self.use_button.clicked.connect(self._use)\n        close_button = QPushButton(\"Закрыть\")\n""",
)
replace_once(
    "src/geoworkbench/ui/header_catalog_dialog.py",
    """        right = QVBoxLayout()\n        right.addWidget(self.details)\n        form = QFormLayout()\n        form.addRow(\"Рекомендуемая ориентация\", self.orientation)\n        right.addLayout(form)\n        right.addStretch(1)\n        if selection_mode:\n            right.addWidget(self.use_button)\n        right.addWidget(close_button)\n""",
    """        right = QVBoxLayout()\n        right.addWidget(self.preview, 1)\n        right.addWidget(self.details)\n        form = QFormLayout()\n        form.addRow(\"Рекомендуемая ориентация\", self.orientation)\n        right.addLayout(form)\n        right.addWidget(self.preview_button)\n        if selection_mode:\n            right.addWidget(self.use_button)\n        right.addWidget(close_button)\n""",
)
replace_once(
    "src/geoworkbench/ui/header_catalog_dialog.py",
    """        root = QHBoxLayout(self)\n        root.addLayout(left, 2)\n        root.addLayout(right, 1)\n        self.resize(1050, 560)\n""",
    """        root = QHBoxLayout(self)\n        root.addLayout(left, 1)\n        root.addLayout(right, 2)\n        self.setMinimumSize(1050, 650)\n        self.resize(1500, 900)\n""",
)
replace_once(
    "src/geoworkbench/ui/header_catalog_dialog.py",
    """        if item is None:\n            self.details.clear()\n            return\n""",
    """        if item is None:\n            self.details.clear()\n            self.preview.set_template(None)\n            self.preview_button.setEnabled(False)\n            return\n        try:\n            template = resolve_catalog_header(\n                self.controller.session.project.masterlog_templates, item.catalog_id\n            )\n        except KeyError:\n            template = None\n        self.preview.set_template(template)\n        self.preview_button.setEnabled(template is not None)\n""",
)
replace_once(
    "src/geoworkbench/ui/header_catalog_dialog.py",
    """    def _edit(self) -> None:\n""",
    """    def _open_preview(self) -> None:\n        item = self._selected_item()\n        if item is None:\n            return\n        try:\n            template = resolve_catalog_header(\n                self.controller.session.project.masterlog_templates, item.catalog_id\n            )\n        except KeyError as exc:\n            QMessageBox.warning(self, self.windowTitle(), str(exc))\n            return\n        HeaderPreviewDialog(\n            template, self.controller.session, self, language=self.language\n        ).exec()\n\n    def _edit(self) -> None:\n""",
)

replace_once(
    "src/geoworkbench/ui/print_center_dialog.py",
    "from PySide6.QtCore import Qt\n",
    "from PySide6.QtCore import QSize, Qt\nfrom PySide6.QtGui import QPixmap\n",
)
replace_once(
    "src/geoworkbench/ui/print_center_dialog.py",
    "HeaderCatalogCallback = Callable[[], tuple[tuple[str, str], ...]]\n",
    "HeaderCatalogCallback = Callable[[], tuple[tuple[str, str], ...]]\nHeaderPreviewCallback = Callable[[str], QPixmap | None]\nHeaderEditCallback = Callable[[str], None]\n",
)
replace_once(
    "src/geoworkbench/ui/print_center_dialog.py",
    """        manage_headers_callback: HeaderCatalogCallback | None = None,\n    ) -> None:\n""",
    """        manage_headers_callback: HeaderCatalogCallback | None = None,\n        header_preview_callback: HeaderPreviewCallback | None = None,\n        edit_header_callback: HeaderEditCallback | None = None,\n    ) -> None:\n""",
)
replace_once(
    "src/geoworkbench/ui/print_center_dialog.py",
    """        self.manage_headers_callback = manage_headers_callback\n        page = initial_page or PrintPageSettings()\n""",
    """        self.manage_headers_callback = manage_headers_callback\n        self.header_preview_callback = header_preview_callback\n        self.edit_header_callback = edit_header_callback\n        page = initial_page or PrintPageSettings()\n""",
)
replace_once(
    "src/geoworkbench/ui/print_center_dialog.py",
    """        header_layout = QHBoxLayout(header_group)\n        self.header_combo = QComboBox()\n        self.header_combo.setObjectName(\"print-header-template-combo\")\n        self.manage_headers_button = QPushButton(\n""",
    """        header_layout = QVBoxLayout(header_group)\n        header_controls = QHBoxLayout()\n        self.header_combo = QComboBox()\n        self.header_combo.setObjectName(\"print-header-template-combo\")\n        self.header_combo.currentIndexChanged.connect(self._refresh_header_preview)\n        self.manage_headers_button = QPushButton(\n""",
)
replace_once(
    "src/geoworkbench/ui/print_center_dialog.py",
    """        self.manage_headers_button.clicked.connect(self._manage_headers)\n        self.manage_headers_button.setEnabled(manage_headers_callback is not None)\n        header_layout.addWidget(self.header_combo, 1)\n        header_layout.addWidget(self.manage_headers_button)\n        root.addWidget(header_group)\n        self._set_header_choices(self.header_choices, initial_header_template_id)\n""",
    """        self.manage_headers_button.clicked.connect(self._manage_headers)\n        self.manage_headers_button.setEnabled(manage_headers_callback is not None)\n        self.edit_header_button = QPushButton(\n            {\n                AppLanguage.RU: \"Развернуть / редактировать...\",\n                AppLanguage.KK: \"Ашу / өңдеу...\",\n                AppLanguage.EN: \"Open / edit...\",\n            }[language]\n        )\n        self.edit_header_button.clicked.connect(self._open_header_editor)\n        self.edit_header_button.setEnabled(False)\n        header_controls.addWidget(self.header_combo, 1)\n        header_controls.addWidget(self.manage_headers_button)\n        header_controls.addWidget(self.edit_header_button)\n        header_layout.addLayout(header_controls)\n        self.header_preview = QLabel()\n        self.header_preview.setObjectName(\"print-center-header-preview\")\n        self.header_preview.setAlignment(Qt.AlignmentFlag.AlignCenter)\n        self.header_preview.setMinimumHeight(190)\n        self.header_preview.setStyleSheet(\n            \"QLabel { background: #e5e7eb; border: 1px solid #94a3b8; }\"\n        )\n        header_layout.addWidget(self.header_preview)\n        root.addWidget(header_group)\n        self._set_header_choices(self.header_choices, initial_header_template_id)\n        self._refresh_header_preview()\n""",
)
replace_once(
    "src/geoworkbench/ui/print_center_dialog.py",
    """        self._set_header_choices(\n            self.header_choices,\n            str(current) if isinstance(current, str) else None,\n        )\n\n    def _dpi(self) -> int:\n""",
    """        self._set_header_choices(\n            self.header_choices,\n            str(current) if isinstance(current, str) else None,\n        )\n        self._refresh_header_preview()\n\n    def _refresh_header_preview(self, _index: int | None = None) -> None:\n        raw = self.header_combo.currentData()\n        catalog_id = str(raw) if isinstance(raw, str) and raw.strip() else None\n        self.edit_header_button.setEnabled(\n            catalog_id is not None and self.edit_header_callback is not None\n        )\n        if catalog_id is None or self.header_preview_callback is None:\n            self.header_preview.clear()\n            self.header_preview.setText(\n                {\n                    AppLanguage.RU: \"Шапка не выбрана\",\n                    AppLanguage.KK: \"Тақырып таңдалмады\",\n                    AppLanguage.EN: \"No header selected\",\n                }[self.localizer.language]\n            )\n            return\n        try:\n            pixmap = self.header_preview_callback(catalog_id)\n        except (KeyError, RuntimeError, ValueError):\n            pixmap = None\n        if pixmap is None or pixmap.isNull():\n            self.header_preview.setText(\n                {\n                    AppLanguage.RU: \"Предпросмотр недоступен\",\n                    AppLanguage.KK: \"Алдын ала қарау қолжетімсіз\",\n                    AppLanguage.EN: \"Preview unavailable\",\n                }[self.localizer.language]\n            )\n            return\n        target = QSize(max(600, self.header_preview.width() - 8), 180)\n        self.header_preview.setPixmap(\n            pixmap.scaled(\n                target,\n                Qt.AspectRatioMode.KeepAspectRatio,\n                Qt.TransformationMode.SmoothTransformation,\n            )\n        )\n\n    def _open_header_editor(self) -> None:\n        raw = self.header_combo.currentData()\n        if not isinstance(raw, str) or not raw.strip() or self.edit_header_callback is None:\n            return\n        self.edit_header_callback(raw)\n        self._refresh_header_preview()\n\n    def _dpi(self) -> int:\n""",
)

replace_once(
    "src/geoworkbench/ui/main_window.py",
    "from geoworkbench.printing.header_catalog import catalog_items, resolve_catalog_header\n",
    "from geoworkbench.printing.header_catalog import catalog_items, resolve_catalog_header\nfrom geoworkbench.ui.header_preview_widget import render_header_preview_pixmap\n",
)
replace_once(
    "src/geoworkbench/ui/main_window.py",
    """            manage_headers_callback=self._manage_print_headers,\n        )\n""",
    """            manage_headers_callback=self._manage_print_headers,\n            header_preview_callback=self._print_header_preview_pixmap,\n            edit_header_callback=self._open_print_header_from_center,\n        )\n""",
)
replace_once(
    "src/geoworkbench/ui/main_window.py",
    """    def _manage_print_headers(self) -> tuple[tuple[str, str], ...]:\n        self.show_header_catalog()\n        return self._print_header_choices()\n\n    def _resolve_print_header(self, job: PrintJobSettings):\n""",
    """    def _manage_print_headers(self) -> tuple[tuple[str, str], ...]:\n        self.show_header_catalog()\n        return self._print_header_choices()\n\n    def _print_header_preview_pixmap(self, catalog_id: str) -> QPixmap | None:\n        try:\n            template = resolve_catalog_header(\n                self.session.project.masterlog_templates, catalog_id\n            )\n        except KeyError:\n            return None\n        return render_header_preview_pixmap(\n            template, self.session, QSize(1200, 320),\n            language=self.language, mode=\"header\"\n        )\n\n    def _open_print_header_from_center(self, catalog_id: str) -> None:\n        dialog = HeaderCatalogDialog(\n            self.masterlog_template_controller, self, language=self.language\n        )\n        dialog.refresh(catalog_id)\n        dialog.exec()\n        self._update_title()\n\n    def _resolve_print_header(self, job: PrintJobSettings):\n""",
)

replace_once(
    "src/geoworkbench/ui/masterlog_header_dialog.py",
    """    QGraphicsView,\n    QHBoxLayout,\n""",
    """    QGraphicsView,\n    QGroupBox,\n    QHBoxLayout,\n""",
)
replace_once(
    "src/geoworkbench/ui/masterlog_header_dialog.py",
    "from geoworkbench.ui.logo_catalog_dialog import LogoCatalogDialog\n",
    "from geoworkbench.ui.logo_catalog_dialog import LogoCatalogDialog\nfrom geoworkbench.ui.header_preview_widget import HeaderPreviewWidget\n",
)
replace_once(
    "src/geoworkbench/ui/masterlog_header_dialog.py",
    """        self.preview.setTransformationAnchor(QGraphicsView.ViewportAnchor.AnchorUnderMouse)\n\n        self.height_input = QDoubleSpinBox()\n""",
    """        self.preview.setTransformationAnchor(QGraphicsView.ViewportAnchor.AnchorUnderMouse)\n        self.overview = HeaderPreviewWidget(controller.session, self, language=language)\n        self.overview.setObjectName(\"masterlog-header-overview\")\n        self.overview.setMinimumHeight(230)\n\n        self.height_input = QDoubleSpinBox()\n""",
)
replace_once(
    "src/geoworkbench/ui/masterlog_header_dialog.py",
    """        self.fit_button = QPushButton(_TEXT[language][\"fit\"])\n        self.fit_button.clicked.connect(self._fit_preview)\n\n        left_buttons = QHBoxLayout()\n""",
    """        self.fit_button = QPushButton(_TEXT[language][\"fit\"])\n        self.fit_button.clicked.connect(self._fit_preview)\n        self.edit_zoom_button = QPushButton(\n            {AppLanguage.RU: \"Увеличить для правки\", AppLanguage.KK: \"Өңдеу үшін үлкейту\", AppLanguage.EN: \"Editing zoom\"}[language]\n        )\n        self.edit_zoom_button.clicked.connect(self._fit_editing_preview)\n        self.fit_page_button = QPushButton(\n            {AppLanguage.RU: \"Подогнать шапку к странице\", AppLanguage.KK: \"Тақырыпты бетке сыйғызу\", AppLanguage.EN: \"Fit header to page\"}[language]\n        )\n        self.fit_page_button.clicked.connect(self._fit_header_to_page)\n\n        left_buttons = QHBoxLayout()\n""",
)
replace_once(
    "src/geoworkbench/ui/masterlog_header_dialog.py",
    """        left_buttons.addWidget(self.preset_button)\n        left_buttons.addWidget(self.fit_button)\n""",
    """        left_buttons.addWidget(self.preset_button)\n        left_buttons.addWidget(self.edit_zoom_button)\n        left_buttons.addWidget(self.fit_button)\n""",
)
replace_once(
    "src/geoworkbench/ui/masterlog_header_dialog.py",
    """        right_layout.addWidget(hint)\n        right_layout.addWidget(self.page_info_label)\n        right_layout.addWidget(self.preview, 1)\n\n        splitter = QSplitter(Qt.Orientation.Horizontal)\n        splitter.addWidget(left)\n        splitter.addWidget(right)\n        splitter.setStretchFactor(0, 0)\n        splitter.setStretchFactor(1, 1)\n        splitter.setSizes([340, 760])\n""",
    """        right_layout.addWidget(hint)\n        right_layout.addWidget(self.page_info_label)\n        right_layout.addWidget(QLabel({AppLanguage.RU: \"Обзор всей шапки (всегда видна целиком)\", AppLanguage.KK: \"Тақырыптың толық шолуы\", AppLanguage.EN: \"Whole-header overview\"}[language]))\n        right_layout.addWidget(self.overview, 1)\n        right_layout.addWidget(QLabel({AppLanguage.RU: \"Рабочий холст: перетаскивание, прокрутка и точная правка\", AppLanguage.KK: \"Жұмыс кенебі: жылжыту, айналдыру және дәл өңдеу\", AppLanguage.EN: \"Editing canvas: drag, scroll and precise adjustment\"}[language]))\n        right_layout.addWidget(self.preview, 2)\n\n        inspector = QGroupBox({AppLanguage.RU: \"Выбранный элемент\", AppLanguage.KK: \"Таңдалған элемент\", AppLanguage.EN: \"Selected element\"}[language])\n        inspector_layout = QVBoxLayout(inspector)\n        self.inspector_title = QLabel(\"—\")\n        self.inspector_title.setWordWrap(True)\n        inspector_layout.addWidget(self.inspector_title)\n        inspector_form = QFormLayout()\n        self.geometry_inputs = [QDoubleSpinBox() for _ in range(4)]\n        for label, control in zip((\"X, мм\", \"Y, мм\", \"Ширина, мм\", \"Высота, мм\"), self.geometry_inputs, strict=True):\n            control.setRange(0.0, 5000.0)\n            control.setDecimals(2)\n            control.editingFinished.connect(self._apply_inspector_geometry)\n            inspector_form.addRow(label, control)\n        inspector_layout.addLayout(inspector_form)\n        self.inspector_bounds = QLabel()\n        self.inspector_bounds.setWordWrap(True)\n        inspector_layout.addWidget(self.inspector_bounds)\n        inspector_edit_button = QPushButton({AppLanguage.RU: \"Содержимое и стиль...\", AppLanguage.KK: \"Мазмұны мен стилі...\", AppLanguage.EN: \"Content and style...\"}[language])\n        inspector_edit_button.clicked.connect(self._edit)\n        inspector_layout.addWidget(inspector_edit_button)\n        inspector_layout.addWidget(self.fit_page_button)\n        inspector_layout.addStretch(1)\n        autosave = QLabel({AppLanguage.RU: \"Изменения сразу сохраняются в проект. «Сохранить в каталог» создаёт отдельную повторно используемую шапку.\", AppLanguage.KK: \"Өзгерістер жобаға бірден сақталады. «Каталогқа сақтау» бөлек қайта қолданылатын тақырып жасайды.\", AppLanguage.EN: \"Changes are saved to the project immediately. Save to catalog creates a separate reusable header.\"}[language])\n        autosave.setWordWrap(True)\n        inspector_layout.addWidget(autosave)\n\n        splitter = QSplitter(Qt.Orientation.Horizontal)\n        splitter.addWidget(left)\n        splitter.addWidget(right)\n        splitter.addWidget(inspector)\n        splitter.setStretchFactor(0, 0)\n        splitter.setStretchFactor(1, 1)\n        splitter.setStretchFactor(2, 0)\n        splitter.setSizes([300, 850, 300])\n""",
)
replace_once(
    "src/geoworkbench/ui/masterlog_header_dialog.py",
    """        self.preview_scene.clear()\n        page_width, page_height = self._page_size_mm()\n""",
    """        self.preview_scene.clear()\n        self.overview.set_template(self.template)\n        page_width, page_height = self._page_size_mm()\n""",
)
replace_once(
    "src/geoworkbench/ui/masterlog_header_dialog.py",
    """                line_graphic.setPen(self._line_pen(element))\n                line_graphic.setToolTip(json.dumps(element.properties, ensure_ascii=False))\n                self.preview_scene.addItem(line_graphic)\n""",
    """                line_graphic.setPen(self._line_pen(element))\n                line_graphic.setToolTip(json.dumps(element.properties, ensure_ascii=False))\n                line_graphic.setSelected(element.element_id == selected)\n                self.preview_scene.addItem(line_graphic)\n""",
)
replace_once(
    "src/geoworkbench/ui/masterlog_header_dialog.py",
    """            rect_graphic.setBrush(QBrush(fill))\n            rect_graphic.setToolTip(json.dumps(element.properties, ensure_ascii=False))\n            self.preview_scene.addItem(rect_graphic)\n""",
    """            rect_graphic.setBrush(QBrush(fill))\n            rect_graphic.setToolTip(json.dumps(element.properties, ensure_ascii=False))\n            rect_graphic.setSelected(element.element_id == selected)\n            self.preview_scene.addItem(rect_graphic)\n""",
)
replace_once(
    "src/geoworkbench/ui/masterlog_header_dialog.py",
    """        if self._fit_on_refresh:\n            self._fit_preview()\n            self._fit_on_refresh = False\n\n\n    def _page_size_mm(self) -> tuple[float, float]:\n""",
    """        self._refresh_inspector()\n        if self._fit_on_refresh:\n            self._fit_editing_preview()\n            self._fit_on_refresh = False\n\n\n    def _page_size_mm(self) -> tuple[float, float]:\n""",
)
replace_once(
    "src/geoworkbench/ui/masterlog_header_dialog.py",
    """    def _fit_preview(self) -> None:\n        self.preview.resetTransform()\n        self.preview.fitInView(self.preview_scene.sceneRect(), Qt.AspectRatioMode.KeepAspectRatio)\n\n    def _apply_height(self) -> None:\n""",
    """    def _fit_preview(self) -> None:\n        self.preview.resetTransform()\n        self.preview.fitInView(self.preview_scene.sceneRect(), Qt.AspectRatioMode.KeepAspectRatio)\n\n    def _fit_editing_preview(self) -> None:\n        scene = self.preview_scene.sceneRect()\n        if scene.isEmpty():\n            return\n        self.preview.resetTransform()\n        viewport_height = max(220.0, float(self.preview.viewport().height()) * 0.72)\n        scale = min(14.0, max(1.0, viewport_height / max(1.0, scene.height())))\n        self.preview.scale(scale, scale)\n        self.preview.centerOn(scene.left(), scene.center().y())\n        self.preview.horizontalScrollBar().setValue(self.preview.horizontalScrollBar().minimum())\n\n    def _refresh_inspector(self) -> None:\n        element = self._selected()\n        enabled = element is not None\n        for control in self.geometry_inputs:\n            control.setEnabled(enabled)\n        if element is None:\n            self.inspector_title.setText(\"—\")\n            self.inspector_bounds.clear()\n            return\n        self.inspector_title.setText(f\"<b>{self._preview_text(element)}</b><br>{element.element_type}\")\n        for control, value in zip(self.geometry_inputs, (element.x_mm, element.y_mm, element.width_mm, element.height_mm), strict=True):\n            control.blockSignals(True)\n            control.setValue(value)\n            control.blockSignals(False)\n        page_width, _page_height = self._page_size_mm()\n        right = element.x_mm + element.width_mm\n        bottom = element.y_mm + element.height_mm\n        outside = right > page_width + 1e-6 or bottom > self.template.header_height_mm + 1e-6\n        self.inspector_bounds.setText(\n            f\"Правая граница: {right:g} / {page_width:g} мм<br>Нижняя граница: {bottom:g} / {self.template.header_height_mm:g} мм\"\n            + (\"<br><b style='color:#b91c1c'>Элемент выходит за границы шапки</b>\" if outside else \"\")\n        )\n\n    def _apply_inspector_geometry(self) -> None:\n        element = self._selected()\n        if element is None:\n            return\n        x, y, width, height = (control.value() for control in self.geometry_inputs)\n        try:\n            self.controller.update_header_element(\n                self.template_id, element.element_id, element_type=element.element_type,\n                x_mm=x, y_mm=y, width_mm=width, height_mm=height, properties=element.properties\n            )\n            lower = y + height\n            if lower > self.template.header_height_mm:\n                self.controller.update_header_height(self.template_id, min(500.0, lower + 2.0))\n        except ValueError as exc:\n            QMessageBox.warning(self, self.windowTitle(), str(exc))\n            self._refresh_inspector()\n            return\n        self._selected_element_id = element.element_id\n        self.refresh()\n\n    def _fit_header_to_page(self) -> None:\n        page_width, _page_height = self._page_size_mm()\n        question = {AppLanguage.RU: \"Пропорционально подогнать все элементы шапки в ширину текущей страницы?\", AppLanguage.KK: \"Тақырыптың барлық элементтерін ағымдағы бет еніне пропорционалды сыйғызу керек пе?\", AppLanguage.EN: \"Proportionally fit all header elements to the current page width?\"}[self.localizer.language]\n        if QMessageBox.question(self, self.windowTitle(), question) != QMessageBox.StandardButton.Yes:\n            return\n        try:\n            self.controller.fit_header_to_page(self.template_id, page_width)\n        except ValueError as exc:\n            QMessageBox.warning(self, self.windowTitle(), str(exc))\n            return\n        self._fit_on_refresh = True\n        self.refresh()\n\n    def _apply_height(self) -> None:\n""",
)
replace_once(
    "src/geoworkbench/ui/masterlog_header_dialog.py",
    """    def _list_selection_changed(self, current, _previous) -> None:\n        if current is not None:\n            self._selected_element_id = str(current.data(Qt.ItemDataRole.UserRole))\n""",
    """    def _list_selection_changed(self, current, _previous) -> None:\n        if current is not None:\n            self._selected_element_id = str(current.data(Qt.ItemDataRole.UserRole))\n        self._refresh_inspector()\n""",
)
replace_once(
    "src/geoworkbench/ui/masterlog_header_dialog.py",
    """        self._selected_element_id = element_id\n        self.refresh()\n\n    def _add(self) -> None:\n""",
    """        lower = y + element.height_mm\n        if lower > self.template.header_height_mm:\n            try:\n                self.controller.update_header_height(self.template_id, min(500.0, lower + 2.0))\n            except ValueError:\n                pass\n        self._selected_element_id = element_id\n        self.refresh()\n\n    def _add(self) -> None:\n""",
)

append_once(
    "tests/test_header_catalog.py",
    "    assert target.header_elements == []\n",
    """\n\ndef test_fit_header_to_page_scales_geometry_and_expands_height() -> None:\n    controller = _controller()\n    template = controller.create_header_template(\"Wide header\")\n    template.header_elements = []\n    first = controller.add_header_element(\n        template.template_id, element_type=\"text\", x_mm=100.0, y_mm=5.0,\n        width_mm=300.0, height_mm=20.0,\n        properties={\"text\": \"Wide\", \"font_size_mm\": 6.0},\n    )\n    second = controller.add_header_element(\n        template.template_id, element_type=\"field\", x_mm=420.0, y_mm=35.0,\n        width_mm=160.0, height_mm=30.0,\n        properties={\"field\": \"well.name\", \"font_size_mm\": 4.0},\n    )\n    scale = controller.fit_header_to_page(template.template_id, 210.0)\n    assert 0.0 < scale < 1.0\n    assert min(item.x_mm for item in template.header_elements) == 2.0\n    assert max(item.x_mm + item.width_mm for item in template.header_elements) <= 208.0\n    assert template.header_height_mm >= max(item.y_mm + item.height_mm for item in template.header_elements)\n    fitted_first = next(item for item in template.header_elements if item.element_id == first.element_id)\n    fitted_second = next(item for item in template.header_elements if item.element_id == second.element_id)\n    assert fitted_first.properties[\"font_size_mm\"] < 6.0\n    assert fitted_second.properties[\"font_size_mm\"] < 4.0\n""",
)
append_once(
    "docs/PRINT_HEADER_AND_LOGO_CATALOGS.md",
    "- ссылка логотипа на отсутствующий image asset блокирует загрузку повреждённого проекта.\n",
    """\n\n## Развёрнутый визуальный просмотр и редактор\n\nКаталог шапок показывает реальный WYSIWYG-предпросмотр выбранного шаблона тем же painter, который\nиспользуется для PDF и физической печати. Доступны два режима: крупный вид только шапки и лист\nцеликом. Предпросмотр можно открыть в отдельном масштабируемом окне.\n\nРедактор шапки содержит одновременно полный обзор композиции, увеличенный рабочий холст с\nгоризонтальной прокруткой и постоянный инспектор выбранного элемента. В инспекторе доступны точные\nкоординаты X/Y, ширина, высота, содержимое и стиль. Перемещение или изменение элемента ниже\nтекущей границы автоматически увеличивает высоту шапки. Команда «Подогнать шапку к странице»\nпропорционально нормализует импортированную SKF-композицию в ширину текущего A3/A4/custom листа.\nЦентр печати также показывает выбранную шапку до запуска общего предпросмотра документа.\n""",
)
replace_once(
    "docs/CHANGELOG.md",
    "## Unreleased\n\n",
    "## Unreleased\n\n- Доработан визуальный редактор печатных шапок: WYSIWYG-предпросмотр в каталоге и центре печати, отдельный развёрнутый просмотр, полный обзор плюс увеличенный рабочий холст, постоянный инспектор X/Y/ширины/высоты и пропорциональная подгонка импортированной SKF-шапки к странице.\n\n",
)

print("Visual header editor patch applied")
