from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def replace_once(path: Path, old: str, new: str, label: str) -> None:
    text = path.read_text(encoding="utf-8")
    count = text.count(old)
    if count != 1:
        raise RuntimeError(f"{label}: expected one match, found {count}")
    path.write_text(text.replace(old, new, 1), encoding="utf-8")


def insert_before(path: Path, marker: str, addition: str, label: str) -> None:
    text = path.read_text(encoding="utf-8")
    count = text.count(marker)
    if count != 1:
        raise RuntimeError(f"{label}: expected one marker, found {count}")
    path.write_text(text.replace(marker, addition + marker, 1), encoding="utf-8")


# 1. SKF shape geometry: never turn ordinary separators/frames into accidental diagonals.
importer = ROOT / "src/geoworkbench/importers/skf_importer.py"
replace_once(
    importer,
    '''    if _is_shape(component):
        return MasterlogHeaderElement(
            str(uuid4()),
            "line",
            x,
            y,
            width,
            height,
            {
                "color": _color(component),
                "line_width": max(0.2, _float_property(component, "Pen.Width", "LineWidth", default=1.0)),
                "source_component": component.name,
            },
        )
''',
    '''    if _is_shape(component):
        shape_kind = _shape_kind(component)
        resolved_kind, shape_width, shape_height = _normalize_shape_geometry(
            width, height, shape_kind
        )
        if resolved_kind == "frame":
            return MasterlogHeaderElement(
                str(uuid4()),
                "text",
                x,
                y,
                width,
                height,
                {
                    "text": "",
                    "frame": True,
                    "color": _color(component),
                    "font_size_mm": 1.5,
                    "source_component": component.name,
                    "source_shape_kind": shape_kind,
                },
            )
        return MasterlogHeaderElement(
            str(uuid4()),
            "line",
            x,
            y,
            shape_width,
            shape_height,
            {
                "color": _color(component),
                "width": max(
                    0.2,
                    _float_property(component, "Pen.Width", "LineWidth", default=1.0),
                ),
                "source_component": component.name,
                "source_shape_kind": resolved_kind,
            },
        )
''',
    "replace SKF shape conversion",
)
insert_before(
    importer,
    '''def _is_shape(component: DelphiComponent) -> bool:
''',
    '''def _shape_kind(component: DelphiComponent) -> str:
    raw = str(
        get_property(
            component,
            "Shape",
            "ShapeType",
            "Kind",
            "LineType",
            "Orientation",
            "Style",
            default="",
        )
    ).casefold()
    token = f"{component.class_name} {component.name} {raw}".casefold()
    if any(value in token for value in ("rectangle", "rect", "box", "frame", "border")):
        return "frame"
    if any(value in token for value in ("horizontal", "horiz", "topline", "bottomline")):
        return "horizontal"
    if any(value in token for value in ("vertical", "vert", "leftline", "rightline")):
        return "vertical"
    if any(value in token for value in ("diagonal", "diag", "slash")):
        return "diagonal"
    return "unknown"


def _normalize_shape_geometry(
    width_mm: float,
    height_mm: float,
    shape_kind: str,
) -> tuple[str, float, float]:
    width = max(0.0, float(width_mm))
    height = max(0.0, float(height_mm))
    if shape_kind == "frame":
        return "frame", width, height
    if shape_kind == "horizontal":
        return "horizontal", max(width, height, 1.0), 0.0
    if shape_kind == "vertical":
        return "vertical", 0.0, max(width, height, 1.0)
    if shape_kind == "diagonal":
        return "diagonal", width, height

    shorter = min(width, height)
    longer = max(width, height)
    if shorter <= 1.2 or (shorter > 0.0 and longer / shorter >= 4.0):
        if width >= height:
            return "horizontal", max(width, 1.0), 0.0
        return "vertical", 0.0, max(height, 1.0)
    return "frame", width, height


''',
    "insert SKF shape helpers",
)

# 2. Expanded preview: two large views plus direct transition to the editor.
preview_path = ROOT / "src/geoworkbench/ui/header_preview_widget.py"
replace_once(
    preview_path,
    "from copy import deepcopy\n",
    "from collections.abc import Callable\nfrom copy import deepcopy\n",
    "add Callable import",
)
replace_once(
    preview_path,
    '''    QGraphicsView,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QVBoxLayout,
    QWidget,
''',
    '''    QGraphicsView,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QSplitter,
    QVBoxLayout,
    QWidget,
''',
    "add preview widgets",
)
old_preview_dialog = '''class HeaderPreviewDialog(QDialog):
    def __init__(
        self,
        template: MasterlogTemplate,
        session: ProjectSession,
        parent: QWidget | None = None,
        *,
        language: AppLanguage = AppLanguage.RU,
    ) -> None:
        super().__init__(parent)
        self.setWindowTitle(
            {
                AppLanguage.RU: f"Предпросмотр шапки — {template.name}",
                AppLanguage.KK: f"Тақырыпты алдын ала қарау — {template.name}",
                AppLanguage.EN: f"Header preview — {template.name}",
            }[language]
        )
        self.setMinimumSize(900, 560)
        self.resize(1400, 850)
        preview = HeaderPreviewWidget(session, self, language=language)
        preview.set_template(template)
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Close)
        buttons.rejected.connect(self.reject)
        buttons.button(QDialogButtonBox.StandardButton.Close).clicked.connect(self.accept)
        layout = QVBoxLayout(self)
        layout.addWidget(preview, 1)
        layout.addWidget(buttons)
'''
new_preview_dialog = '''class HeaderPreviewDialog(QDialog):
    def __init__(
        self,
        template: MasterlogTemplate,
        session: ProjectSession,
        parent: QWidget | None = None,
        *,
        language: AppLanguage = AppLanguage.RU,
        edit_callback: Callable[[], None] | None = None,
    ) -> None:
        super().__init__(parent)
        self._edit_callback = edit_callback
        self.setWindowTitle(
            {
                AppLanguage.RU: f"Предпросмотр и проверка шапки — {template.name}",
                AppLanguage.KK: f"Тақырыпты алдын ала қарау және тексеру — {template.name}",
                AppLanguage.EN: f"Header preview and inspection — {template.name}",
            }[language]
        )
        self.setMinimumSize(1100, 680)
        self.resize(1700, 980)

        hint = QLabel(
            {
                AppLanguage.RU: (
                    "Слева шапка показана крупно для проверки текста и блоков; справа — её реальный "
                    "размер на печатном листе. Масштаб каждого вида настраивается независимо."
                ),
                AppLanguage.KK: (
                    "Сол жақта мәтін мен блоктарды тексеру үшін тақырып ірі көрсетіледі; оң жақта "
                    "баспа бетіндегі нақты орналасуы көрсетіледі."
                ),
                AppLanguage.EN: (
                    "The left pane shows a close-up for checking text and blocks; the right pane "
                    "shows the real placement on the printed page. Each view has independent zoom."
                ),
            }[language]
        )
        hint.setWordWrap(True)

        close_up_group = QGroupBox(
            {AppLanguage.RU: "Шапка крупно", AppLanguage.KK: "Тақырып ірі", AppLanguage.EN: "Header close-up"}[language]
        )
        close_up_layout = QVBoxLayout(close_up_group)
        self.close_up_preview = HeaderPreviewWidget(session, close_up_group, language=language)
        self.close_up_preview.mode.setCurrentIndex(
            max(0, self.close_up_preview.mode.findData("header"))
        )
        self.close_up_preview.set_template(template)
        close_up_layout.addWidget(self.close_up_preview)

        page_group = QGroupBox(
            {AppLanguage.RU: "Лист целиком", AppLanguage.KK: "Толық бет", AppLanguage.EN: "Whole page"}[language]
        )
        page_layout = QVBoxLayout(page_group)
        self.page_preview = HeaderPreviewWidget(session, page_group, language=language)
        self.page_preview.mode.setCurrentIndex(
            max(0, self.page_preview.mode.findData("page"))
        )
        self.page_preview.set_template(template)
        page_layout.addWidget(self.page_preview)

        splitter = QSplitter(Qt.Orientation.Horizontal)
        splitter.setChildrenCollapsible(False)
        splitter.addWidget(close_up_group)
        splitter.addWidget(page_group)
        splitter.setSizes([1050, 650])

        fullscreen_button = QPushButton(
            {AppLanguage.RU: "Полный экран", AppLanguage.KK: "Толық экран", AppLanguage.EN: "Full screen"}[language]
        )
        fullscreen_button.clicked.connect(self._toggle_fullscreen)
        edit_button = QPushButton(
            {AppLanguage.RU: "Редактировать шапку…", AppLanguage.KK: "Тақырыпты өңдеу…", AppLanguage.EN: "Edit header…"}[language]
        )
        edit_button.setEnabled(edit_callback is not None)
        edit_button.clicked.connect(self._open_editor)
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Close)
        buttons.rejected.connect(self.reject)
        buttons.button(QDialogButtonBox.StandardButton.Close).clicked.connect(self.accept)
        footer = QHBoxLayout()
        footer.addWidget(fullscreen_button)
        footer.addWidget(edit_button)
        footer.addStretch(1)
        footer.addWidget(buttons)

        layout = QVBoxLayout(self)
        layout.addWidget(hint)
        layout.addWidget(splitter, 1)
        layout.addLayout(footer)

    def _toggle_fullscreen(self) -> None:
        if self.isMaximized():
            self.showNormal()
        else:
            self.showMaximized()

    def _open_editor(self) -> None:
        callback = self._edit_callback
        if callback is None:
            return
        self.accept()
        callback()
'''
replace_once(
    preview_path,
    old_preview_dialog,
    new_preview_dialog,
    "replace expanded preview dialog",
)

# 3. Catalog preview can enter the real editor directly.
catalog = ROOT / "src/geoworkbench/ui/header_catalog_dialog.py"
replace_once(
    catalog,
    '''        HeaderPreviewDialog(
            template, self.controller.session, self, language=self.language
        ).exec()
''',
    '''        HeaderPreviewDialog(
            template,
            self.controller.session,
            self,
            language=self.language,
            edit_callback=self._edit,
        ).exec()
''',
    "connect preview to editor",
)

# 4. Full-screen header workspace, side-by-side views and contextual assistant.
header_dialog = ROOT / "src/geoworkbench/ui/masterlog_header_dialog.py"
replace_once(
    header_dialog,
    "from geoworkbench.ui.adaptive_toolbar import AdaptiveActionToolBar\n",
    "from geoworkbench.ui.adaptive_toolbar import AdaptiveActionToolBar\nfrom geoworkbench.ui.header_visual_assistant import HeaderVisualAssistant\n",
    "import visual assistant",
)
replace_once(
    header_dialog,
    '''        self.fit_page_button.clicked.connect(self._fit_header_to_page)

        self.toolbar = AdaptiveActionToolBar(parent=self)
''',
    '''        self.fit_page_button.clicked.connect(self._fit_header_to_page)
        self.fullscreen_button = QPushButton(
            {
                AppLanguage.RU: "Полный экран",
                AppLanguage.KK: "Толық экран",
                AppLanguage.EN: "Full screen",
            }[language]
        )
        self.fullscreen_button.clicked.connect(self._toggle_fullscreen)
        self.dual_view_button = QPushButton(
            {
                AppLanguage.RU: "Два вида рядом",
                AppLanguage.KK: "Екі көрініс қатар",
                AppLanguage.EN: "Views side by side",
            }[language]
        )
        self.dual_view_button.setCheckable(True)
        self.dual_view_button.clicked.connect(self._toggle_dual_view)

        self.toolbar = AdaptiveActionToolBar(parent=self)
''',
    "add header workspace buttons",
)
replace_once(
    header_dialog,
    '''            self.edit_zoom_button,
            self.fit_button,
        ):
''',
    '''            self.edit_zoom_button,
            self.fit_button,
            self.dual_view_button,
            self.fullscreen_button,
        ):
''',
    "add workspace buttons to toolbar",
)
replace_once(
    header_dialog,
    '''        self.inspector_bounds = QLabel()
        self.inspector_bounds.setWordWrap(True)
        inspector_layout.addWidget(self.inspector_bounds)
        inspector_edit_button = QPushButton({AppLanguage.RU: "Содержимое и стиль...", AppLanguage.KK: "Мазмұны мен стилі...", AppLanguage.EN: "Content and style..."}[language])
''',
    '''        self.inspector_bounds = QLabel()
        self.inspector_bounds.setWordWrap(True)
        inspector_layout.addWidget(self.inspector_bounds)
        self.visual_assistant = HeaderVisualAssistant(
            inspector,
            language=language,
        )
        self.visual_assistant.text_requested.connect(self._assistant_set_text)
        self.visual_assistant.field_requested.connect(self._assistant_set_field)
        self.visual_assistant.line_orientation_requested.connect(
            self._assistant_set_line_orientation
        )
        self.visual_assistant.properties_requested.connect(self._edit)
        inspector_layout.addWidget(self.visual_assistant)
        inspector_edit_button = QPushButton({AppLanguage.RU: "Содержимое и стиль...", AppLanguage.KK: "Мазмұны мен стилі...", AppLanguage.EN: "Content and style..."}[language])
''',
    "insert visual assistant",
)
replace_once(
    header_dialog,
    '''        if preview_state is not None:
            self.preview_splitter.restoreState(preview_state)
        else:
            self.preview_splitter.setSizes([260, 520])

        close_buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Close)
''',
    '''        if preview_state is not None:
            self.preview_splitter.restoreState(preview_state)
        else:
            self.preview_splitter.setSizes([260, 520])
        preview_orientation = str(
            settings_store.value("ui/masterlog_header/preview_orientation", "vertical")
        )
        side_by_side = preview_orientation == "horizontal"
        self.dual_view_button.setChecked(side_by_side)
        self.preview_splitter.setOrientation(
            Qt.Orientation.Horizontal if side_by_side else Qt.Orientation.Vertical
        )

        close_buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Close)
''',
    "restore preview orientation",
)
replace_once(
    header_dialog,
    '''        settings.setValue("ui/masterlog_header/main_splitter", self.main_splitter.saveState())
        settings.setValue("ui/masterlog_header/preview_splitter", self.preview_splitter.saveState())
''',
    '''        settings.setValue("ui/masterlog_header/main_splitter", self.main_splitter.saveState())
        settings.setValue("ui/masterlog_header/preview_splitter", self.preview_splitter.saveState())
        settings.setValue(
            "ui/masterlog_header/preview_orientation",
            "horizontal"
            if self.preview_splitter.orientation() == Qt.Orientation.Horizontal
            else "vertical",
        )
''',
    "save preview orientation",
)
replace_once(
    header_dialog,
    "                line_graphic.setToolTip(json.dumps(element.properties, ensure_ascii=False))\n",
    "                line_graphic.setToolTip(self._element_tooltip(element))\n",
    "human line tooltip",
)
replace_once(
    header_dialog,
    "            rect_graphic.setToolTip(json.dumps(element.properties, ensure_ascii=False))\n",
    "            rect_graphic.setToolTip(self._element_tooltip(element))\n",
    "human block tooltip",
)
replace_once(
    header_dialog,
    '''        if element is None:
            self.inspector_title.setText("—")
            self.inspector_bounds.clear()
            return
''',
    '''        page_width, _page_height = self._page_size_mm()
        if element is None:
            self.inspector_title.setText("—")
            self.inspector_bounds.clear()
            self.visual_assistant.set_element(
                None,
                page_width_mm=page_width,
                header_height_mm=self.template.header_height_mm,
            )
            return
''',
    "assistant no selection",
)
replace_once(
    header_dialog,
    '''        page_width, _page_height = self._page_size_mm()
        right = element.x_mm + element.width_mm
''',
    '''        right = element.x_mm + element.width_mm
''',
    "reuse page width",
)
replace_once(
    header_dialog,
    '''        self.inspector_bounds.setText(
            f"Правая граница: {right:g} / {page_width:g} мм<br>Нижняя граница: {bottom:g} / {self.template.header_height_mm:g} мм"
            + ("<br><b style='color:#b91c1c'>Элемент выходит за границы шапки</b>" if outside else "")
        )

    def _apply_inspector_geometry(self) -> None:
''',
    '''        self.inspector_bounds.setText(
            f"Правая граница: {right:g} / {page_width:g} мм<br>Нижняя граница: {bottom:g} / {self.template.header_height_mm:g} мм"
            + ("<br><b style='color:#b91c1c'>Элемент выходит за границы шапки</b>" if outside else "")
        )
        self.visual_assistant.set_element(
            element,
            page_width_mm=page_width,
            header_height_mm=self.template.header_height_mm,
        )

    def _toggle_fullscreen(self) -> None:
        if self.isMaximized():
            self.showNormal()
        else:
            self.showMaximized()

    def _toggle_dual_view(self, checked: bool) -> None:
        self.preview_splitter.setOrientation(
            Qt.Orientation.Horizontal if checked else Qt.Orientation.Vertical
        )
        if checked:
            self.preview_splitter.setSizes([700, 900])
        else:
            self.preview_splitter.setSizes([280, 620])

    def _assistant_set_text(self, value: str) -> None:
        element = self._selected()
        if element is None or element.element_type != "text":
            return
        properties = dict(element.properties)
        properties["text"] = value
        self._assistant_update_element(element, properties=properties)

    def _assistant_set_field(self, field_name: str) -> None:
        element = self._selected()
        if element is None or element.element_type != "field" or not field_name:
            return
        properties = dict(element.properties)
        properties["field"] = field_name
        self._assistant_update_element(element, properties=properties)

    def _assistant_set_line_orientation(self, orientation: str) -> None:
        element = self._selected()
        if element is None or element.element_type != "line":
            return
        if orientation == "horizontal":
            width = max(10.0, element.width_mm, element.height_mm)
            height = 0.0
        else:
            width = 0.0
            height = max(10.0, element.height_mm, element.width_mm)
        properties = dict(element.properties)
        properties["source_shape_kind"] = orientation
        self._assistant_update_element(
            element,
            width_mm=width,
            height_mm=height,
            properties=properties,
        )

    def _assistant_update_element(
        self,
        element: MasterlogHeaderElement,
        *,
        width_mm: float | None = None,
        height_mm: float | None = None,
        properties: dict[str, object] | None = None,
    ) -> None:
        try:
            self.controller.update_header_element(
                self.template_id,
                element.element_id,
                element_type=element.element_type,
                x_mm=element.x_mm,
                y_mm=element.y_mm,
                width_mm=element.width_mm if width_mm is None else width_mm,
                height_mm=element.height_mm if height_mm is None else height_mm,
                properties=element.properties if properties is None else properties,
            )
        except ValueError as exc:
            QMessageBox.warning(self, self.windowTitle(), str(exc))
            return
        self._selected_element_id = element.element_id
        self.refresh()

    def _element_tooltip(self, element: MasterlogHeaderElement) -> str:
        type_name = {
            "text": "Текст",
            "field": "Автоматическое поле",
            "image": "Изображение / логотип",
            "line": "Линия",
            "lithotype_swatch": "Образец литотипа",
            "lithology_legend": "Литологическая легенда",
            "lba_legend": "Легенда ЛБА",
        }.get(element.element_type, element.element_type)
        content = self._preview_text(element).replace("\n", " ")
        source = element.properties.get("source_component")
        source_text = f"\nИсточник SKF: {source}" if isinstance(source, str) and source else ""
        print_warning = ""
        if element.element_type == "line" and element.width_mm > 0.5 and element.height_mm > 0.5:
            print_warning = "\nВнимание: диагональ будет напечатана как видна."
        return (
            f"{type_name}\nСодержимое: {content}\n"
            f"X={element.x_mm:g}, Y={element.y_mm:g}, "
            f"размер={element.width_mm:g}×{element.height_mm:g} мм"
            f"{source_text}{print_warning}\nДвойной щелчок — все свойства."
        )

    def _apply_inspector_geometry(self) -> None:
''',
    "insert workspace and assistant methods",
)

# 5. Tablet/form editor: full-screen control and a contextual visual explanation.
tablet_editor = ROOT / "src/geoworkbench/ui/tablet_track_editor_dialog.py"
replace_once(
    tablet_editor,
    '''        self.toolbar.add_standard_action(
            self._text("Удалить", "Жою", "Remove"),
            self._remove,
            icon=QStyle.StandardPixmap.SP_TrashIcon,
        )
        self.toolbar.add_stretch()
''',
    '''        self.toolbar.add_standard_action(
            self._text("Удалить", "Жою", "Remove"),
            self._remove,
            icon=QStyle.StandardPixmap.SP_TrashIcon,
        )
        self.toolbar.add_standard_action(
            self._text("Полный экран", "Толық экран", "Full screen"),
            self._toggle_fullscreen,
            icon=QStyle.StandardPixmap.SP_TitleBarMaxButton,
        )
        self.toolbar.add_stretch()
''',
    "add tablet fullscreen action",
)
replace_once(
    tablet_editor,
    '''        preview_hint.setWordWrap(True)
        preview_layout.addWidget(preview_hint)
        self.preview = TabletTrackPreviewWidget(self.track, preview_group)
''',
    '''        preview_hint.setWordWrap(True)
        preview_layout.addWidget(preview_hint)
        self.preview_assistant = QLabel()
        self.preview_assistant.setWordWrap(True)
        self.preview_assistant.setStyleSheet(
            "background:#eff6ff; border:1px solid #bfdbfe; padding:6px; color:#1e3a8a;"
        )
        preview_layout.addWidget(self.preview_assistant)
        self.preview = TabletTrackPreviewWidget(self.track, preview_group)
''',
    "add tablet visual assistant",
)
replace_once(
    tablet_editor,
    '''    def _text(self, ru: str, kk: str, en: str) -> str:
''',
    '''    def _toggle_fullscreen(self) -> None:
        if self.isMaximized():
            self.showNormal()
        else:
            self.showMaximized()

    def _text(self, ru: str, kk: str, en: str) -> str:
''',
    "insert tablet fullscreen method",
)
replace_once(
    tablet_editor,
    '''    def _refresh_preview(self, *_args) -> None:
        if self._loading:
            return
        self.preview.set_track(self._track_from_controls())
''',
    '''    def _refresh_preview(self, *_args) -> None:
        if self._loading:
            return
        candidate = self._track_from_controls()
        self.preview.set_track(candidate)
        selected_row = self._selected_row()
        selected_curve = (
            candidate.curve_mnemonics[selected_row]
            if 0 <= selected_row < len(candidate.curve_mnemonics)
            else ""
        )
        assistant_text = self._text(
            (
                f"Сейчас редактируется дорожка «{candidate.title}». "
                + (f"Выбран параметр {selected_curve}. " if selected_curve else "")
                + "Название, ширина, сетка, шкала и стиль кривой уже показаны справа так, как будут выглядеть при печати."
            ),
            (
                f"Қазір «{candidate.title}» жолы өңделуде. "
                + (f"Таңдалған параметр: {selected_curve}. " if selected_curve else "")
                + "Атау, ені, торы, шкаласы және қисық стилі оң жақта баспа түрінде көрсетілген."
            ),
            (
                f"Editing track ‘{candidate.title}’. "
                + (f"Selected parameter: {selected_curve}. " if selected_curve else "")
                + "The title, width, grid, scale and curve style are already shown as they will print."
            ),
        )
        self.preview_assistant.setText(assistant_text)
''',
    "enhance tablet live explanation",
)

# 6. Current documentation and changelog travel with the product change.
docs = ROOT / "docs/PRINT_HEADER_AND_LOGO_CATALOGS.md"
with docs.open("a", encoding="utf-8") as handle:
    handle.write(
        "\n\n## Полноэкранная правка и визуальный помощник\n\n"
        "Развёрнутый просмотр показывает одновременно крупную шапку и её положение на полном "
        "печатном листе. Из каталога можно сразу перейти в редактор. Редактор поддерживает полный "
        "экран и размещение обзора и рабочего холста рядом; выбранная компоновка сохраняется.\n\n"
        "Панель «Визуальный помощник» объясняет назначение выбранного блока, показывает источник SKF "
        "и предупреждения о выходе за границы. Для текста и динамического поля доступны быстрый ввод "
        "и вставка. Для линий доступны команды горизонтального и вертикального выравнивания; "
        "диагональ помечается как реально печатаемый элемент. При импорте SKF обычные разделители "
        "нормализуются по доминирующей оси, а прямоугольные рамки больше не превращаются в диагонали.\n"
    )

changelog = ROOT / "docs/CHANGELOG.md"
replace_once(
    changelog,
    "## Unreleased\n\n",
    "## Unreleased\n\n- Добавлен полноэкранный визуальный редактор шапок и форм: два крупных вида одновременно, контекстный помощник с быстрым вводом текста и полей, исправление диагональных SKF-разделителей и команды горизонтального/вертикального выравнивания линий.\n\n",
    "update changelog",
)
