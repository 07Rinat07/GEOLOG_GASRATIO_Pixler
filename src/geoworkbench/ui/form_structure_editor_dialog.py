from __future__ import annotations

from PySide6.QtCore import QRectF, Qt
from PySide6.QtGui import QColor, QPainter, QPen
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDialog,
    QFormLayout,
    QGroupBox,
    QHeaderView,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QScrollArea,
    QSpinBox,
    QSplitter,
    QTreeWidget,
    QTreeWidgetItem,
    QVBoxLayout,
    QWidget,
)

from geoworkbench.domain.models import Dataset
from geoworkbench.domain.text_presentation import (
    TEXT_ORIENTATIONS,
    TEXT_VERTICAL_POSITIONS,
)
from geoworkbench.forms.a4_layout import A4FitError, fit_form_to_a4, form_fits_a4
from geoworkbench.forms.draft import DraftFormController
from geoworkbench.forms.editor import FormStructureEditor
from geoworkbench.forms.models import (
    FormDocument,
    FormPageOrientation,
    FormTrack,
)
from geoworkbench.forms.preview import FormPreviewController, PreviewCallback
from geoworkbench.forms.repository import FormRepository
from geoworkbench.printing.form_width_advisor import FormWidthLevel, audit_form_width
from geoworkbench.printing.text_rendering import draw_oriented_text
from geoworkbench.tablet.grid_geometry import normalized_grid_lines
from geoworkbench.tablet.models import TrackKind, minimum_width_for_track_kinds
from geoworkbench.tablet.vertical_ruler import (
    VerticalRulerMode,
    supports_inner_vertical_ruler,
)
from geoworkbench.ui.grid_settings_widget import GridSettingsWidget
from geoworkbench.ui.track_content_editor_dialog import TrackContentEditorDialog
from geoworkbench.ui.vertical_ruler_settings_widget import (
    VerticalRulerSettingsWidget,
)

_ITEM_KIND_ROLE = Qt.ItemDataRole.UserRole
_ITEM_ID_ROLE = Qt.ItemDataRole.UserRole + 1


class _FormPreview(QWidget):
    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self._form: FormDocument | None = None
        self._selected_id: str | None = None
        self.setMinimumHeight(150)

    def set_form(self, form: FormDocument, selected_id: str | None = None) -> None:
        self._form = form
        self._selected_id = selected_id
        self.update()

    def paintEvent(self, _event) -> None:  # noqa: N802 - Qt API
        painter = QPainter(self)
        painter.fillRect(self.rect(), QColor("#f7f8fa"))
        form = self._form
        if form is None or not form.columns:
            painter.setPen(QColor("#596273"))
            painter.drawText(self.rect(), Qt.AlignmentFlag.AlignCenter, "—")
            return
        margin = 10
        available = max(1, self.width() - margin * 2)
        total_width = max(1, sum(column.width for column in form.columns if column.visible))
        x = margin
        for column in form.columns:
            if not column.visible:
                continue
            width = max(34, round(available * column.width / total_width))
            rect = self.rect().adjusted(x, margin, x + width - self.width(), -margin)
            selected = self._selected_id == column.column_id
            painter.fillRect(rect, QColor("#dbeafe") if selected else QColor("#ffffff"))
            painter.setPen(
                QPen(QColor("#2563eb") if selected else QColor("#9aa4b2"), 2 if selected else 1)
            )
            painter.drawRect(rect)
            column_header_height = 48 if column.title_orientation != "horizontal" else 25
            header = rect.adjusted(4, 3, -4, -rect.height() + column_header_height)
            painter.setPen(QColor("#111827"))
            draw_oriented_text(
                painter,
                QRectF(header),
                column.title,
                orientation=column.title_orientation,
                position=column.title_position,
                padding_x=1.0,
                padding_y=1.0,
            )
            visible_tracks = [track for track in column.tracks if track.visible]
            if visible_tracks:
                track_height = max(
                    24,
                    (rect.height() - column_header_height - 7) // len(visible_tracks),
                )
                top = rect.top() + column_header_height + 3
                for track in visible_tracks:
                    track_rect = rect.adjusted(
                        4, top - rect.top(), -4, top + track_height - rect.bottom()
                    )
                    track_selected = self._selected_id == track.track_id
                    painter.fillRect(
                        track_rect, QColor("#fef3c7") if track_selected else QColor("#f3f4f6")
                    )
                    self._draw_track_grid(painter, track_rect, track)
                    painter.setPen(
                        QPen(
                            QColor("#d97706") if track_selected else QColor("#c4cad3"),
                            2 if track_selected else 1,
                        )
                    )
                    painter.drawRect(track_rect)
                    painter.setPen(QColor("#374151"))
                    draw_oriented_text(
                        painter,
                        QRectF(track_rect.adjusted(3, 0, -3, 0)),
                        track.title,
                        orientation=track.title_orientation,
                        position=track.title_position,
                    )
                    top += track_height
            x += width

        audit = audit_form_width(
            column.width if column.visible else 0 for column in form.columns
        )
        boundaries = (
            (audit.portrait_capacity_px, "A4 книжн.", QColor("#dc2626")),
            (audit.landscape_capacity_px, "A4 альбомн.", QColor("#d97706")),
        )
        for capacity_px, caption, color in boundaries:
            if audit.total_width_px <= capacity_px or audit.total_width_px <= 0:
                continue
            boundary_x = margin + round(available * capacity_px / audit.total_width_px)
            painter.setPen(QPen(color, 1, Qt.PenStyle.DashLine))
            painter.drawLine(boundary_x, margin, boundary_x, self.height() - margin)
            painter.setPen(color)
            painter.drawText(boundary_x + 3, margin + 12, caption)

    @staticmethod
    def _draw_track_grid(painter: QPainter, rect, track: FormTrack) -> None:
        """Draw a compact preview of the track's effective grid settings."""

        if not (track.grid_x or track.grid_y) or track.grid_alpha <= 0.0:
            return
        painter.save()
        try:
            base_alpha = max(0, min(255, round(track.grid_alpha * 255)))
            major_color = QColor("#64748b")
            major_color.setAlpha(base_alpha)
            minor_color = QColor("#94a3b8")
            minor_color.setAlpha(round(base_alpha * 0.55))

            if track.grid_x:
                divisions = normalized_grid_lines(
                    track.grid_major_divisions,
                    track.grid_minor_divisions,
                )
                minor_spacing = rect.width() / max(
                    1,
                    track.grid_major_divisions * track.grid_minor_divisions,
                )
                for line in divisions:
                    if line.fraction <= 0.0 or line.fraction >= 1.0:
                        continue
                    if not line.major and minor_spacing < 3.0:
                        continue
                    painter.setPen(QPen(major_color if line.major else minor_color, 1))
                    x = rect.left() + round(rect.width() * line.fraction)
                    painter.drawLine(x, rect.top() + 1, x, rect.bottom() - 1)

            if track.grid_y:
                # The real axis is aligned globally at a five-unit step.  This
                # miniature has no data range, so five equal bands communicate
                # that standard without inventing depth labels.
                painter.setPen(QPen(major_color, 1))
                for index in range(1, 5):
                    y = rect.top() + round(rect.height() * index / 5)
                    painter.drawLine(rect.left() + 1, y, rect.right() - 1, y)
        finally:
            painter.restore()


class FormStructureEditorDialog(QDialog):
    def __init__(
        self,
        form: FormDocument,
        repository: FormRepository,
        parent=None,
        *,
        language: str = "ru",
        dataset: Dataset | None = None,
        preview_callback: PreviewCallback | None = None,
    ) -> None:
        super().__init__(parent)
        self.repository = repository
        self.dataset = dataset
        self.language = language
        self.draft = DraftFormController.create(form)
        self.editor = FormStructureEditor(self.draft.form)
        self.preview_controller = FormPreviewController(preview_callback)
        self.saved_form: FormDocument | None = None
        self._updating_properties = False
        self._base_title = self._text(
            "Редактор структуры формы", "Пішін құрылымының редакторы", "Form structure editor"
        )
        self.setWindowTitle(self._base_title)
        self.resize(1080, 680)

        root = QVBoxLayout(self)
        form_properties = QFormLayout()
        self.form_name_edit = QLineEdit(self.editor.form.name)
        self.form_name_edit.editingFinished.connect(self._apply_form_name)
        form_properties.addRow(
            self._text("Название формы", "Пішін атауы", "Form name"), self.form_name_edit
        )
        self.page_orientation_combo = QComboBox()
        self.page_orientation_combo.setObjectName("form-editor-page-orientation")
        self.page_orientation_combo.addItem(
            self._text("A4 — книжная", "A4 — кітаптық", "A4 — portrait"),
            FormPageOrientation.PORTRAIT.value,
        )
        self.page_orientation_combo.addItem(
            self._text("A4 — альбомная", "A4 — альбомдық", "A4 — landscape"),
            FormPageOrientation.LANDSCAPE.value,
        )
        orientation_index = self.page_orientation_combo.findData(
            self.editor.form.preferred_page_orientation.value
        )
        self.page_orientation_combo.setCurrentIndex(max(0, orientation_index))
        self.page_orientation_combo.currentIndexChanged.connect(
            self._apply_page_orientation
        )
        self.page_orientation_combo.setToolTip(
            self._text(
                "Предпросмотр и проверка ширины используют выбранную ориентацию A4.",
                "Алдын ала қарау және енді тексеру таңдалған A4 бағытын қолданады.",
                "Preview and width validation use the selected A4 orientation.",
            )
        )
        form_properties.addRow(
            self._text("Целевой лист", "Мақсатты парақ", "Target sheet"),
            self.page_orientation_combo,
        )
        root.addLayout(form_properties)

        splitter = QSplitter(Qt.Orientation.Horizontal)
        root.addWidget(splitter, 1)

        left = QWidget()
        left_layout = QVBoxLayout(left)
        self.tree = QTreeWidget()
        self.tree.setHeaderLabels(
            [
                self._text("Структура", "Құрылым", "Structure"),
                self._text("Тип", "Түрі", "Type"),
                self._text("Ширина", "Ені", "Width"),
                self._text("Состояние", "Күйі", "Status"),
            ]
        )
        tree_header = self.tree.header()
        tree_header.setStretchLastSection(False)
        tree_header.setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        for column_index in (1, 2):
            tree_header.setSectionResizeMode(
                column_index,
                QHeaderView.ResizeMode.ResizeToContents,
            )
        tree_header.setSectionResizeMode(3, QHeaderView.ResizeMode.Interactive)
        tree_header.resizeSection(3, 160)
        self.tree.currentItemChanged.connect(self._selection_changed)
        left_layout.addWidget(self.tree, 1)

        column_buttons = QHBoxLayout()
        self._button(
            column_buttons, self._text("+ Колонка", "+ Баған", "+ Column"), self._add_column
        )
        self._button(
            column_buttons, self._text("− Колонка", "− Баған", "− Column"), self._remove_column
        )
        self._button(column_buttons, "↑", self._move_up)
        self._button(column_buttons, "↓", self._move_down)
        left_layout.addLayout(column_buttons)

        track_buttons = QHBoxLayout()
        self._button(track_buttons, self._text("+ Дорожка", "+ Жол", "+ Track"), self._add_track)
        self._button(track_buttons, self._text("− Дорожка", "− Жол", "− Track"), self._remove_track)
        self._button(
            track_buttons, self._text("Содержимое", "Мазмұны", "Content"), self._edit_track_content
        )
        left_layout.addLayout(track_buttons)
        splitter.addWidget(left)

        right = QWidget()
        right_layout = QVBoxLayout(right)
        right_layout.addWidget(
            QLabel(
                self._text(
                    "Предпросмотр структуры", "Құрылымды алдын ала қарау", "Structure preview"
                )
            )
        )
        self.preview = _FormPreview()
        right_layout.addWidget(self.preview)
        self.width_advice = QLabel()
        self.width_advice.setWordWrap(True)
        self.width_advice.setTextFormat(Qt.TextFormat.RichText)
        right_layout.addWidget(self.width_advice)
        width_actions = QHBoxLayout()
        self.fit_a4_button = QPushButton(
            self._text(
                "Автоподбор ширины под A4",
                "A4 үшін енді автотаңдау",
                "Auto-fit widths to A4",
            )
        )
        self.fit_a4_button.setObjectName("form-auto-fit-a4")
        self.fit_a4_button.setToolTip(
            self._text(
                "Пропорционально уменьшить видимые колонки, сохранив минимальную ширину служебных и графических дорожек.",
                "Көрінетін бағандарды қызметтік және графикалық жолдардың ең аз енін сақтай отырып пропорционалды азайту.",
                "Reduce visible columns proportionally while preserving safe minimum widths.",
            )
        )
        self.fit_a4_button.clicked.connect(self._fit_to_selected_a4)
        width_actions.addWidget(self.fit_a4_button)
        width_actions.addStretch(1)
        right_layout.addLayout(width_actions)

        settings_widget = QWidget()
        settings_layout = QVBoxLayout(settings_widget)
        settings_layout.setContentsMargins(0, 0, 0, 0)
        properties = QFormLayout()
        self.title_edit = QLineEdit()
        self.title_edit.editingFinished.connect(self._apply_title)
        properties.addRow(self._text("Заголовок", "Тақырып", "Title"), self.title_edit)

        self.visible_check = QCheckBox()
        self.visible_check.setAccessibleName(
            self._text(
                "Видимость выбранной колонки или дорожки",
                "Таңдалған бағанның немесе жолдың көрінуі",
                "Selected column or track visibility",
            )
        )
        self.visible_check.setToolTip(
            self._text(
                "Скрытый элемент не показывается в форме и не выводится на печать.",
                "Жасырын элемент пішінде көрсетілмейді және басып шығарылмайды.",
                "A hidden item is omitted from the form and from print.",
            )
        )
        self.visible_check.toggled.connect(self._apply_visibility)
        properties.addRow(
            self._text("Видимость", "Көрінуі", "Visibility"), self.visible_check
        )

        self.title_orientation_combo = QComboBox()
        orientation_labels = {
            "horizontal": self._text("Горизонтально (0°)", "Көлденең (0°)", "Horizontal (0°)"),
            "vertical_bottom_to_top": self._text(
                "Вертикально снизу вверх (90°)",
                "Төменнен жоғары тік (90°)",
                "Vertical bottom to top (90°)",
            ),
            "vertical_top_to_bottom": self._text(
                "Вертикально сверху вниз (90°)",
                "Жоғарыдан төмен тік (90°)",
                "Vertical top to bottom (90°)",
            ),
        }
        for value in TEXT_ORIENTATIONS:
            self.title_orientation_combo.addItem(orientation_labels[value], value)
        self.title_orientation_combo.currentIndexChanged.connect(
            self._apply_title_presentation
        )
        properties.addRow(
            self._text("Направление текста", "Мәтін бағыты", "Text direction"),
            self.title_orientation_combo,
        )

        self.title_position_combo = QComboBox()
        position_labels = {
            "top": self._text("Ближе к верху", "Жоғарыға жақын", "Near top"),
            "center": self._text("По центру", "Ортада", "Centred"),
            "bottom": self._text("Ближе к низу", "Төменге жақын", "Near bottom"),
        }
        for value in TEXT_VERTICAL_POSITIONS:
            self.title_position_combo.addItem(position_labels[value], value)
        self.title_position_combo.currentIndexChanged.connect(
            self._apply_title_presentation
        )
        properties.addRow(
            self._text("Положение текста", "Мәтін орны", "Text position"),
            self.title_position_combo,
        )

        self.group_edit = QLineEdit()
        self.group_edit.setPlaceholderText(
            self._text("Например: Геология", "Мысалы: Геология", "For example: Geology")
        )
        self.group_edit.editingFinished.connect(self._apply_group_title)
        properties.addRow(
            self._text("Раздел формы", "Пішін бөлімі", "Form section"), self.group_edit
        )

        self.width_spin = QSpinBox()
        self.width_spin.setRange(48, 2000)
        self.width_spin.setSuffix(" px")
        self.width_spin.valueChanged.connect(self._apply_width)
        properties.addRow(
            self._text("Ширина колонки", "Баған ені", "Column width"), self.width_spin
        )

        self.kind_combo = QComboBox()
        for kind in TrackKind:
            self.kind_combo.addItem(self._track_kind_name(kind), kind)
        self.kind_combo.currentIndexChanged.connect(self._apply_track_kind)
        properties.addRow(self._text("Тип дорожки", "Жол түрі", "Track type"), self.kind_combo)

        self.axis_label_edit = QLineEdit()
        self.axis_label_edit.editingFinished.connect(self._apply_axis_label)
        self.show_interval_labels_check = QCheckBox(
            self._text(
                "Показывать подписи поверх литотипа",
                "Литотип үстіндегі жазуларды көрсету",
                "Show labels over lithotype",
            )
        )
        self.show_interval_labels_check.toggled.connect(self._apply_interval_labels)
        properties.addRow(
            self._text("Подпись оси X", "X осінің жазуы", "X-axis label"),
            self.axis_label_edit,
        )
        properties.addRow(
            self._text("Подписи интервалов", "Интервал жазулары", "Interval labels"),
            self.show_interval_labels_check,
        )

        self.lba_label_orientation_label = QLabel(
            self._text(
                "Направление подписей «Цвет / Битум»",
                "«Түс / Битум» жазуларының бағыты",
                "Colour / Bitumen label direction",
            )
        )
        self.lba_label_orientation_combo = QComboBox()
        for value in TEXT_ORIENTATIONS:
            self.lba_label_orientation_combo.addItem(
                orientation_labels[value], value
            )
        self.lba_label_orientation_combo.currentIndexChanged.connect(
            self._apply_lba_label_orientation
        )
        properties.addRow(
            self.lba_label_orientation_label,
            self.lba_label_orientation_combo,
        )
        self.lba_label_orientation_label.setVisible(False)
        self.lba_label_orientation_combo.setVisible(False)
        settings_layout.addLayout(properties)

        self.grid_group = QGroupBox(
            self._text(
                "Сетка выбранной дорожки",
                "Таңдалған жолдың торы",
                "Selected track grid",
            )
        )
        grid_layout = QVBoxLayout(self.grid_group)
        self.grid_editor = GridSettingsWidget(language=self.language)
        self.grid_settings = self.grid_editor
        self.grid_editor.settings_changed.connect(self._apply_track_grid)
        grid_layout.addWidget(self.grid_editor)
        self.grid_group.setVisible(False)
        settings_layout.addWidget(self.grid_group)

        self.vertical_ruler_editor = VerticalRulerSettingsWidget(
            language=self.language
        )
        self.vertical_ruler_group = self.vertical_ruler_editor
        self.vertical_ruler_mode_input = self.vertical_ruler_editor.mode_input
        self.vertical_ruler_label_every_input = (
            self.vertical_ruler_editor.label_every_input
        )
        self.vertical_ruler_major_tick_every_input = (
            self.vertical_ruler_editor.major_tick_every_input
        )
        self.vertical_ruler_minor_tick_every_input = (
            self.vertical_ruler_editor.minor_tick_every_input
        )
        self.vertical_ruler_editor.settings_changed.connect(
            self._apply_vertical_ruler
        )
        self.vertical_ruler_group.setVisible(False)
        # Keep the requested per-column ruler control discoverable before the
        # more detailed grid controls in the scrollable inspector.
        settings_layout.insertWidget(1, self.vertical_ruler_group)
        settings_layout.addStretch(1)
        settings_scroll = QScrollArea()
        settings_scroll.setWidgetResizable(True)
        settings_scroll.setWidget(settings_widget)
        right_layout.addWidget(settings_scroll, 1)
        splitter.addWidget(right)
        splitter.setStretchFactor(0, 3)
        splitter.setStretchFactor(1, 2)

        actions = QHBoxLayout()
        self.live_preview_check = QCheckBox(
            self._text("Живой предпросмотр", "Тікелей алдын ала қарау", "Live preview")
        )
        self.live_preview_check.setChecked(True)
        self.live_preview_check.toggled.connect(self._toggle_live_preview)
        actions.addWidget(self.live_preview_check)
        actions.addStretch(1)
        self.apply_button = self._button(
            actions, self._text("Применить", "Қолдану", "Apply"), self._apply_preview
        )
        self.revert_button = self._button(
            actions,
            self._text("Отменить изменения", "Өзгерістерден бас тарту", "Revert"),
            self._revert,
        )
        self.save_button = self._button(
            actions, self._text("Сохранить", "Сақтау", "Save"), self._save
        )
        self.close_button = self._button(
            actions, self._text("Закрыть", "Жабу", "Close"), self.accept
        )
        root.addLayout(actions)
        self._reload_tree()
        self._update_width_advice()
        self._update_dirty_state()

    def _text(self, ru: str, kk: str, en: str) -> str:
        return {"ru": ru, "kk": kk, "en": en}.get(self.language, ru)

    def _track_kind_name(self, kind: TrackKind) -> str:
        names = {
            TrackKind.DEPTH: self._text("Глубина/время", "Тереңдік/уақыт", "Depth/time"),
            TrackKind.CURVE: self._text("График", "График", "Curve"),
            TrackKind.GAS: self._text("Газ", "Газ", "Gas"),
            TrackKind.DEXP: self._text("D-exponent", "D-exponent", "D-exponent"),
            TrackKind.LITHOLOGY: self._text("Литология", "Литология", "Lithology"),
            TrackKind.CUTTINGS: self._text("Шлам", "Шлам", "Cuttings"),
            TrackKind.CALCIMETRY: self._text("Кальциметрия", "Кальциметрия", "Calcimetry"),
            TrackKind.LBA: self._text("ЛБА", "ЛБА", "LBA"),
            TrackKind.STRATIGRAPHY: self._text("Стратиграфия", "Стратиграфия", "Stratigraphy"),
            TrackKind.INTERPRETATION: self._text(
                "Интерпретация", "Интерпретация", "Interpretation"
            ),
            TrackKind.TEXT: self._text("Текст", "Мәтін", "Text"),
        }
        return names[kind]

    def _tree_status(
        self,
        *,
        visible: bool,
        locked: bool = False,
        grid_x: bool | None = None,
        grid_y: bool | None = None,
        grid_print: bool | None = None,
        vertical_ruler_mode: VerticalRulerMode | None = None,
    ) -> str:
        statuses: list[str] = []
        statuses.append(
            self._text("видна", "көрінеді", "visible")
            if visible
            else self._text("скрыта", "жасырын", "hidden")
        )
        if locked:
            statuses.append(self._text("заблокирована", "бұғатталған", "locked"))
        if grid_x is not None and grid_y is not None:
            axes = "/".join(
                axis for axis, enabled in (("X", grid_x), ("Y", grid_y)) if enabled
            )
            statuses.append(
                self._text("сетка выкл.", "тор өшірілген", "grid off")
                if not axes
                else self._text(f"сетка {axes}", f"тор {axes}", f"grid {axes}")
            )
            if axes:
                statuses.append(
                    self._text("печать", "баспа", "print")
                    if grid_print
                    else self._text("только экран", "тек экран", "screen only")
                )
        if vertical_ruler_mode is VerticalRulerMode.OFF:
            statuses.append(
                self._text(
                    "внутр. шкала выкл.",
                    "ішкі шкала өшірілген",
                    "inner ruler off",
                )
            )
        elif vertical_ruler_mode is VerticalRulerMode.TICKS_ONLY:
            statuses.append(
                self._text("только риски", "тек белгілер", "ticks only")
            )
        elif vertical_ruler_mode is VerticalRulerMode.LABELS_AND_TICKS:
            statuses.append(
                self._text("цифры и риски", "сандар мен белгілер", "labels and ticks")
            )
        return " · ".join(statuses)

    def _button(self, layout: QHBoxLayout, caption: str, callback) -> QPushButton:
        button = QPushButton(caption)
        button.clicked.connect(callback)
        layout.addWidget(button)
        return button


    def _update_width_advice(self) -> None:
        audit = audit_form_width(
            column.width if column.visible else 0 for column in self.editor.form.columns
        )
        if audit.visible_columns == 0:
            self.width_advice.setStyleSheet(
                "padding:6px 8px; border:1px solid #94a3b8; border-radius:5px; "
                "background:#f1f5f9; color:#475569;"
            )
            self.width_advice.setText(
                self._text(
                    "В форме нет видимых колонок. Добавьте колонку для проверки A4.",
                    "Пішінде көрінетін баған жоқ. A4 тексеру үшін баған қосыңыз.",
                    "The form has no visible columns. Add a column to check A4.",
                )
            )
            return
        target = self.editor.form.preferred_page_orientation
        target_scale = (
            audit.portrait_scale_percent
            if target is FormPageOrientation.PORTRAIT
            else audit.landscape_scale_percent
        )
        target_fits = form_fits_a4(self.editor.form, target)
        self.fit_a4_button.setEnabled(not target_fits)
        if target_fits:
            color, background = "#166534", "#dcfce7"
            recommendation = self._text(
                "Форма помещается в выбранный A4 без уменьшения при печати.",
                "Пішін таңдалған A4 парағына басып шығару кезінде кішірейтусіз сыяды.",
                "The form fits the selected A4 without print-time reduction.",
            )
        elif audit.level is FormWidthLevel.FITS_LANDSCAPE:
            color, background = "#92400e", "#fef3c7"
            recommendation = self._text(
                "Для книжного A4 уменьшите ширину; для альбомного A4 форма подходит.",
                "Кітаптық A4 үшін енін азайтыңыз; альбомдық A4 үшін пішін жарайды.",
                "Reduce widths for portrait A4; the form fits landscape A4.",
            )
        elif audit.level is FormWidthLevel.NEEDS_FIT:
            color, background = "#9a3412", "#ffedd5"
            recommendation = self._text(
                "Широкая форма: уменьшите самые широкие колонки, скройте второстепенные или включите автоподбор при печати.",
                "Кең пішін: ең кең бағандарды азайтыңыз, қосымша бағандарды жасырыңыз немесе баспада автосыйғызуды қосыңыз.",
                "Wide form: reduce the widest columns, hide secondary tracks, or use fit-to-page.",
            )
        else:
            color, background = "#991b1b", "#fee2e2"
            recommendation = self._text(
                "Слишком широкая форма: разделите её на рабочую и печатную, либо используйте A3/рулон.",
                "Пішін тым кең: жұмыс және баспа пішіндеріне бөліңіз немесе A3/орам қолданыңыз.",
                "Form is too wide: split it into working/print forms or use A3/roll media.",
            )
        text = self._text(
            f"<b>Ширина формы:</b> {audit.visible_columns} колонок, {audit.total_width_px} px ≈ {audit.total_width_mm:.0f} мм. "
            f"Книжный A4: {audit.portrait_scale_percent:.0f}%; альбомный: {audit.landscape_scale_percent:.0f}%. Целевой масштаб: {target_scale:.0f}%.<br>{recommendation}",
            f"<b>Пішін ені:</b> {audit.visible_columns} баған, {audit.total_width_px} px ≈ {audit.total_width_mm:.0f} мм. "
            f"Кітаптық A4: {audit.portrait_scale_percent:.0f}%; альбомдық: {audit.landscape_scale_percent:.0f}%. Мақсатты масштаб: {target_scale:.0f}%.<br>{recommendation}",
            f"<b>Form width:</b> {audit.visible_columns} columns, {audit.total_width_px} px ≈ {audit.total_width_mm:.0f} mm. "
            f"Portrait A4: {audit.portrait_scale_percent:.0f}%; landscape: {audit.landscape_scale_percent:.0f}%. Target scale: {target_scale:.0f}%.<br>{recommendation}",
        )
        self.width_advice.setStyleSheet(
            f"padding:6px 8px; border:1px solid {color}; border-radius:5px; "
            f"background:{background}; color:{color};"
        )
        self.width_advice.setText(text)

    def _apply_page_orientation(self, _index: int = -1) -> None:
        if self._updating_properties:
            return
        value = self.page_orientation_combo.currentData()
        try:
            orientation = FormPageOrientation(str(value))
        except ValueError:
            orientation = FormPageOrientation.PORTRAIT
        if self.editor.form.preferred_page_orientation is orientation:
            return
        self.editor.form.preferred_page_orientation = orientation
        self._form_changed()
        selected = self._selected_ref()
        self.preview.set_form(self.editor.form, selected[1] if selected else None)

    def _fit_to_selected_a4(self) -> None:
        try:
            result = fit_form_to_a4(
                self.editor.form,
                self.editor.form.preferred_page_orientation,
            )
        except (A4FitError, ValueError) as exc:
            QMessageBox.warning(self, self.windowTitle(), str(exc))
            return
        self._reload_tree()
        self._form_changed()
        message = self._text(
            f"Ширина изменена с {result.previous_width_px} до {result.fitted_width_px} px. Изменено колонок: {result.changed_columns}.",
            f"Ені {result.previous_width_px} px-ден {result.fitted_width_px} px-ге өзгертілді. Өзгерген бағандар: {result.changed_columns}.",
            f"Width changed from {result.previous_width_px} to {result.fitted_width_px} px. Columns changed: {result.changed_columns}.",
        )
        QMessageBox.information(self, self.windowTitle(), message)

    def _apply_form_name(self) -> None:
        if self._updating_properties:
            return
        try:
            self.editor.rename_form(self.form_name_edit.text())
            self._form_changed()
        except ValueError as exc:
            QMessageBox.warning(self, self.windowTitle(), str(exc))
            self.form_name_edit.setText(self.editor.form.name)

    def _toggle_live_preview(self, enabled: bool) -> None:
        self.preview_controller.auto_apply = enabled
        if enabled and self.preview_controller.pending:
            self._apply_preview()

    def _form_changed(self) -> None:
        self.draft.changed()
        self.preview_controller.changed(self.editor.form)
        self._update_width_advice()
        self._update_dirty_state()

    def _update_dirty_state(self) -> None:
        suffix = " *" if self.draft.dirty else ""
        self.setWindowTitle(f"{self._base_title} — {self.editor.form.name}{suffix}")
        self.revert_button.setEnabled(self.draft.dirty)

    def _apply_preview(self) -> None:
        try:
            self.editor.form.validate()
            self.preview_controller.apply(self.editor.form)
        except (KeyError, RuntimeError, ValueError) as exc:
            QMessageBox.warning(self, self.windowTitle(), str(exc))

    def _revert(self) -> None:
        restored = self.draft.revert()
        self.editor = FormStructureEditor(restored)
        self.form_name_edit.setText(restored.name)
        self._updating_properties = True
        try:
            index = self.page_orientation_combo.findData(
                restored.preferred_page_orientation.value
            )
            self.page_orientation_combo.setCurrentIndex(max(0, index))
        finally:
            self._updating_properties = False
        self.preview_controller.apply(restored)
        self._reload_tree()
        self._update_dirty_state()

    def _selected_ref(self) -> tuple[str, str] | None:
        item = self.tree.currentItem()
        if item is None:
            return None
        kind = item.data(0, _ITEM_KIND_ROLE)
        object_id = item.data(0, _ITEM_ID_ROLE)
        if isinstance(kind, str) and isinstance(object_id, str):
            return kind, object_id
        return None

    def _reload_tree(self, selected_id: str | None = None) -> None:
        self.tree.clear()
        selected_item: QTreeWidgetItem | None = None
        for column in self.editor.form.columns:
            column_item = QTreeWidgetItem(
                [
                    column.title,
                    self._text("Колонка", "Баған", "Column"),
                    f"{column.width} px",
                    self._tree_status(
                        visible=column.visible,
                        locked=column.locked,
                    ),
                ]
            )
            column_item.setData(0, _ITEM_KIND_ROLE, "column")
            column_item.setData(0, _ITEM_ID_ROLE, column.column_id)
            self.tree.addTopLevelItem(column_item)
            if selected_id == column.column_id:
                selected_item = column_item
            for track in column.tracks:
                track_item = QTreeWidgetItem(
                    [
                        track.title,
                        self._track_kind_name(track.kind),
                        "",
                        self._tree_status(
                            visible=track.visible,
                            locked=track.locked,
                            grid_x=track.grid_x,
                            grid_y=track.grid_y,
                            grid_print=track.grid_print,
                            vertical_ruler_mode=(
                                track.vertical_ruler.mode
                                if supports_inner_vertical_ruler(track.kind.value)
                                else None
                            ),
                        ),
                    ]
                )
                track_item.setData(0, _ITEM_KIND_ROLE, "track")
                track_item.setData(0, _ITEM_ID_ROLE, track.track_id)
                column_item.addChild(track_item)
                if selected_id == track.track_id:
                    selected_item = track_item
                for binding in track.bindings:
                    binding_item = QTreeWidgetItem(
                        [
                            binding.display_name,
                            self._text("Параметр", "Параметр", "Parameter"),
                            "",
                            self._tree_status(visible=binding.visible),
                        ]
                    )
                    binding_item.setData(0, _ITEM_KIND_ROLE, "binding")
                    binding_item.setData(0, _ITEM_ID_ROLE, f"{track.track_id}::{binding.binding_id}")
                    track_item.addChild(binding_item)
                    if selected_id == binding.binding_id:
                        selected_item = binding_item
                track_item.setExpanded(True)
            column_item.setExpanded(True)
        if selected_item is not None:
            self.tree.setCurrentItem(selected_item)
        elif self.tree.topLevelItemCount():
            first_item = self.tree.topLevelItem(0)
            if first_item is not None:
                self.tree.setCurrentItem(first_item)
        self.preview.set_form(self.editor.form, selected_id)
        self._update_width_advice()

    def _selection_changed(self, _current, _previous) -> None:
        ref = self._selected_ref()
        self._updating_properties = True
        try:
            if ref is None:
                self.title_edit.clear()
                self.title_edit.setEnabled(False)
                self.visible_check.setText(
                    self._text("Показывать элемент", "Элементті көрсету", "Show item")
                )
                self.visible_check.setChecked(False)
                self.visible_check.setEnabled(False)
                self.title_orientation_combo.setEnabled(False)
                self.title_position_combo.setEnabled(False)
                self.group_edit.clear()
                self.group_edit.setEnabled(False)
                self.width_spin.setEnabled(False)
                self.kind_combo.setEnabled(False)
                self.axis_label_edit.clear()
                self.axis_label_edit.setEnabled(False)
                self.show_interval_labels_check.setChecked(False)
                self.show_interval_labels_check.setEnabled(False)
                self.lba_label_orientation_label.setVisible(False)
                self.lba_label_orientation_combo.setVisible(False)
                self.grid_group.setVisible(False)
                self.vertical_ruler_group.setVisible(False)
                return
            kind, object_id = ref
            self.title_edit.setEnabled(True)
            self.visible_check.setEnabled(False)
            self.visible_check.setChecked(False)
            self.title_orientation_combo.setEnabled(kind in {"column", "track"})
            self.title_position_combo.setEnabled(kind in {"column", "track"})
            self.axis_label_edit.setEnabled(False)
            self.axis_label_edit.clear()
            self.show_interval_labels_check.setEnabled(False)
            self.show_interval_labels_check.setChecked(False)
            self.lba_label_orientation_label.setVisible(False)
            self.lba_label_orientation_combo.setVisible(False)
            self.grid_group.setVisible(False)
            self.vertical_ruler_group.setVisible(False)
            if kind == "column":
                column = self.editor.column(object_id)
                self.title_edit.setText(column.title)
                self.visible_check.setText(
                    self._text("Показывать колонку", "Бағанды көрсету", "Show column")
                )
                self.visible_check.setChecked(column.visible)
                self.visible_check.setEnabled(not column.locked)
                self.group_edit.setEnabled(True)
                self.group_edit.setText(column.group_title)
                self.width_spin.setEnabled(True)
                self.width_spin.setMinimum(
                    minimum_width_for_track_kinds(track.kind for track in column.tracks)
                )
                self.width_spin.setValue(column.width)
                self.kind_combo.setEnabled(False)
                self._select_combo_data(
                    self.title_orientation_combo, column.title_orientation
                )
                self._select_combo_data(self.title_position_combo, column.title_position)
            elif kind == "track":
                column, track = self.editor.track(object_id)
                self.title_edit.setText(track.title)
                self.visible_check.setText(
                    self._text("Показывать дорожку", "Жолды көрсету", "Show track")
                )
                self.visible_check.setChecked(track.visible)
                editable = not (column.locked or track.locked)
                self.visible_check.setEnabled(editable)
                self.group_edit.clear()
                self.group_edit.setEnabled(False)
                self.width_spin.setEnabled(False)
                self.kind_combo.setEnabled(True)
                self.axis_label_edit.setEnabled(True)
                self.axis_label_edit.setText(track.x_axis_label)
                self.show_interval_labels_check.setEnabled(
                    track.kind in {TrackKind.LITHOLOGY, TrackKind.CUTTINGS}
                )
                self.show_interval_labels_check.setChecked(track.show_interval_labels)
                is_lba = track.kind is TrackKind.LBA
                self.lba_label_orientation_label.setVisible(is_lba)
                self.lba_label_orientation_combo.setVisible(is_lba)
                self.lba_label_orientation_combo.setEnabled(editable)
                self._select_combo_data(
                    self.lba_label_orientation_combo,
                    track.lba_label_orientation,
                )
                self._select_combo_data(
                    self.title_orientation_combo, track.title_orientation
                )
                self._select_combo_data(self.title_position_combo, track.title_position)
                index = self.kind_combo.findData(track.kind)
                if index >= 0:
                    self.kind_combo.setCurrentIndex(index)
                self.grid_editor.set_values(
                    track.grid_x,
                    track.grid_y,
                    track.grid_major_divisions,
                    track.grid_minor_divisions,
                    track.grid_alpha,
                    track.grid_print,
                )
                self.grid_group.setEnabled(editable)
                self.grid_group.setVisible(True)
                supports_ruler = supports_inner_vertical_ruler(track.kind.value)
                self.vertical_ruler_editor.set_settings(
                    track.vertical_ruler,
                    editable=editable,
                )
                self.vertical_ruler_group.setVisible(supports_ruler)
            else:
                track_id, binding_id = object_id.split("::", 1)
                binding = self.editor.binding(track_id, binding_id)
                self.title_edit.setText(binding.display_name)
                self.visible_check.setText(
                    self._text(
                        "Видимость задаётся для дорожки",
                        "Көріну жол үшін орнатылады",
                        "Visibility is set on the track",
                    )
                )
                self.group_edit.clear()
                self.group_edit.setEnabled(False)
                self.width_spin.setEnabled(False)
                self.kind_combo.setEnabled(False)
                self._select_combo_data(self.title_orientation_combo, "horizontal")
                self._select_combo_data(self.title_position_combo, "center")
            self.preview.set_form(self.editor.form, object_id.split("::", 1)[0])
        finally:
            self._updating_properties = False

    @staticmethod
    def _select_combo_data(combo: QComboBox, value: str) -> None:
        index = combo.findData(value)
        combo.setCurrentIndex(index if index >= 0 else 0)

    def _apply_title_presentation(self, _index: int = -1) -> None:
        if self._updating_properties:
            return
        ref = self._selected_ref()
        if ref is None:
            return
        kind, object_id = ref
        orientation = str(self.title_orientation_combo.currentData() or "horizontal")
        position = str(self.title_position_combo.currentData() or "center")
        try:
            if kind == "column":
                self.editor.set_column_title_presentation(
                    object_id, orientation=orientation, position=position
                )
            elif kind == "track":
                self.editor.set_track_title_presentation(
                    object_id, orientation=orientation, position=position
                )
            else:
                return
            self._form_changed()
            self.preview.set_form(self.editor.form, object_id)
        except (KeyError, PermissionError, ValueError) as exc:
            QMessageBox.warning(self, self.windowTitle(), str(exc))

    def _apply_interval_labels(self, enabled: bool) -> None:
        if self._updating_properties:
            return
        ref = self._selected_ref()
        if ref is None or ref[0] != "track":
            return
        try:
            self.editor.set_track_interval_labels(ref[1], enabled)
            self._form_changed()
            self.preview.set_form(self.editor.form, ref[1])
        except (KeyError, PermissionError, ValueError) as exc:
            QMessageBox.warning(self, self.windowTitle(), str(exc))

    def _apply_lba_label_orientation(self, _index: int = -1) -> None:
        if self._updating_properties:
            return
        ref = self._selected_ref()
        if ref is None or ref[0] != "track":
            return
        orientation = str(
            self.lba_label_orientation_combo.currentData()
            or "vertical_bottom_to_top"
        )
        try:
            self.editor.set_track_lba_label_orientation(ref[1], orientation)
            self.preview.set_form(self.editor.form, ref[1])
            self._form_changed()
        except (KeyError, PermissionError, ValueError) as exc:
            QMessageBox.warning(self, self.windowTitle(), str(exc))

    def _apply_visibility(self, visible: bool) -> None:
        if self._updating_properties:
            return
        ref = self._selected_ref()
        if ref is None or ref[0] not in {"column", "track"}:
            return
        try:
            if ref[0] == "column":
                self.editor.set_column_visible(ref[1], visible)
            else:
                self.editor.set_track_visible(ref[1], visible)
            self._reload_tree(ref[1])
            self._form_changed()
        except (KeyError, PermissionError, ValueError) as exc:
            QMessageBox.warning(self, self.windowTitle(), str(exc))
            self._selection_changed(None, None)

    def _apply_track_grid(self) -> None:
        if self._updating_properties:
            return
        ref = self._selected_ref()
        if ref is None or ref[0] != "track":
            return
        grid_x, grid_y, major, minor, alpha, print_grid = self.grid_editor.values()
        try:
            self.editor.set_track_grid(
                ref[1],
                grid_x=grid_x,
                grid_y=grid_y,
                grid_major_divisions=major,
                grid_minor_divisions=minor,
                grid_alpha=alpha,
                grid_print=print_grid,
            )
            self.preview.set_form(self.editor.form, ref[1])
            self._form_changed()
        except (KeyError, PermissionError, ValueError) as exc:
            QMessageBox.warning(self, self.windowTitle(), str(exc))
            self._selection_changed(None, None)

    def _apply_vertical_ruler(self) -> None:
        if self._updating_properties:
            return
        ref = self._selected_ref()
        if ref is None or ref[0] != "track":
            return
        try:
            self.editor.set_track_vertical_ruler(
                ref[1],
                self.vertical_ruler_editor.settings(),
            )
            _column, track = self.editor.track(ref[1])
            current = self.tree.currentItem()
            if current is not None:
                current.setText(
                    3,
                    self._tree_status(
                        visible=track.visible,
                        locked=track.locked,
                        grid_x=track.grid_x,
                        grid_y=track.grid_y,
                        grid_print=track.grid_print,
                        vertical_ruler_mode=track.vertical_ruler.mode,
                    ),
                )
            self.preview.set_form(self.editor.form, ref[1])
            self._form_changed()
        except (KeyError, PermissionError, ValueError) as exc:
            QMessageBox.warning(self, self.windowTitle(), str(exc))
            self._selection_changed(None, None)

    def _apply_title(self) -> None:
        if self._updating_properties:
            return
        ref = self._selected_ref()
        if ref is None:
            return
        try:
            if ref[0] == "column":
                self.editor.rename_column(ref[1], self.title_edit.text())
                selected_id = ref[1]
            elif ref[0] == "track":
                self.editor.rename_track(ref[1], self.title_edit.text())
                selected_id = ref[1]
            else:
                track_id, binding_id = ref[1].split("::", 1)
                self.editor.rename_binding(track_id, binding_id, self.title_edit.text())
                selected_id = binding_id
            self._reload_tree(selected_id)
            self._form_changed()
        except (KeyError, PermissionError, ValueError) as exc:
            QMessageBox.warning(self, self.windowTitle(), str(exc))
            self._selection_changed(None, None)

    def _apply_group_title(self) -> None:
        if self._updating_properties:
            return
        ref = self._selected_ref()
        if ref is None or ref[0] != "column":
            return
        try:
            self.editor.set_column_group(ref[1], self.group_edit.text())
            self.preview.set_form(self.editor.form, ref[1])
            self._form_changed()
        except (KeyError, ValueError) as exc:
            QMessageBox.warning(self, self.windowTitle(), str(exc))
            self._selection_changed(None, None)

    def _apply_width(self, value: int) -> None:
        if self._updating_properties:
            return
        ref = self._selected_ref()
        if ref is None or ref[0] != "column":
            return
        try:
            self.editor.set_column_width(ref[1], value)
            item = self.tree.currentItem()
            if item is not None:
                item.setText(2, f"{value} px")
            self.preview.set_form(self.editor.form, ref[1])
            self._form_changed()
        except (KeyError, ValueError) as exc:
            QMessageBox.warning(self, self.windowTitle(), str(exc))

    def _apply_axis_label(self) -> None:
        if self._updating_properties:
            return
        ref = self._selected_ref()
        if ref is None or ref[0] != "track":
            return
        try:
            self.editor.set_track_axis_label(ref[1], self.axis_label_edit.text())
            self.preview.set_form(self.editor.form, ref[1])
            self._form_changed()
        except (KeyError, PermissionError, ValueError) as exc:
            QMessageBox.warning(self, self.windowTitle(), str(exc))
            self._selection_changed(None, None)

    def _apply_track_kind(self, _index: int) -> None:
        if self._updating_properties:
            return
        ref = self._selected_ref()
        if ref is None or ref[0] != "track":
            return
        kind = self.kind_combo.currentData()
        if not isinstance(kind, TrackKind):
            return
        try:
            self.editor.set_track_kind(ref[1], kind)
            self._reload_tree(ref[1])
            self._form_changed()
        except (KeyError, PermissionError, ValueError) as exc:
            QMessageBox.warning(self, self.windowTitle(), str(exc))

    def _add_column(self) -> None:
        column = self.editor.add_column(self._text("Новая колонка", "Жаңа баған", "New column"))
        self._reload_tree(column.column_id)
        self._form_changed()

    def _remove_column(self) -> None:
        ref = self._selected_ref()
        if ref is None:
            return
        if ref[0] == "column":
            column_id = ref[1]
        elif ref[0] == "binding":
            column_id = self.editor.track(ref[1].split("::", 1)[0])[0].column_id
        else:
            column_id = self.editor.track(ref[1])[0].column_id
        try:
            self.editor.remove_column(column_id)
            self._reload_tree()
            self._form_changed()
        except (KeyError, PermissionError) as exc:
            QMessageBox.warning(self, self.windowTitle(), str(exc))

    def _add_track(self) -> None:
        ref = self._selected_ref()
        if ref is None:
            if not self.editor.form.columns:
                column = self.editor.add_column(
                    self._text("Новая колонка", "Жаңа баған", "New column")
                )
                column_id = column.column_id
            else:
                column_id = self.editor.form.columns[0].column_id
        elif ref[0] == "column":
            column_id = ref[1]
        elif ref[0] == "binding":
            column_id = self.editor.track(ref[1].split("::", 1)[0])[0].column_id
        else:
            column_id = self.editor.track(ref[1])[0].column_id
        try:
            track = self.editor.add_track(
                column_id,
                title=self._text("Новая дорожка", "Жаңа жол", "New track"),
            )
            self._reload_tree(track.track_id)
            self._form_changed()
        except (KeyError, PermissionError, ValueError) as exc:
            QMessageBox.warning(self, self.windowTitle(), str(exc))

    def _edit_track_content(self) -> None:
        ref = self._selected_ref()
        if ref is not None and ref[0] == "binding":
            ref = ("track", ref[1].split("::", 1)[0])
        if ref is None or ref[0] != "track":
            QMessageBox.information(
                self,
                self.windowTitle(),
                self._text(
                    "Выберите дорожку.",
                    "Жолды таңдаңыз.",
                    "Select a track.",
                ),
            )
            return
        dialog = TrackContentEditorDialog(
            self.editor,
            ref[1],
            self,
            dataset=self.dataset,
            language=self.language,
        )
        if dialog.exec() == QDialog.DialogCode.Accepted:
            self._reload_tree(ref[1])
            self._form_changed()

    def _remove_track(self) -> None:
        ref = self._selected_ref()
        if ref is not None and ref[0] == "binding":
            ref = ("track", ref[1].split("::", 1)[0])
        if ref is None or ref[0] != "track":
            return
        try:
            self.editor.remove_track(ref[1])
            self._reload_tree()
            self._form_changed()
        except (KeyError, PermissionError) as exc:
            QMessageBox.warning(self, self.windowTitle(), str(exc))

    def _move_up(self) -> None:
        self._move(-1)

    def _move_down(self) -> None:
        self._move(1)

    def _move(self, delta: int) -> None:
        ref = self._selected_ref()
        if ref is None or ref[0] == "binding":
            return
        try:
            if ref[0] == "column":
                ids = [column.column_id for column in self.editor.form.columns]
                index = ids.index(ref[1])
                self.editor.move_column(ref[1], index + delta)
            else:
                column, _track = self.editor.track(ref[1])
                ids = [track.track_id for track in column.tracks]
                index = ids.index(ref[1])
                self.editor.move_track(ref[1], column.column_id, index + delta)
            self._reload_tree(ref[1])
            self._form_changed()
        except (KeyError, PermissionError, ValueError) as exc:
            QMessageBox.warning(self, self.windowTitle(), str(exc))

    def _save(self) -> None:
        if not form_fits_a4(
            self.editor.form,
            self.editor.form.preferred_page_orientation,
        ):
            answer = QMessageBox.question(
                self,
                self.windowTitle(),
                self._text(
                    "Форма шире выбранного A4. Автоматически подогнать ширины колонок перед сохранением? Нажмите «Нет», чтобы вернуться к ручному редактированию.",
                    "Пішін таңдалған A4-тен кең. Сақтау алдында баған ендерін автоматты түрде сәйкестендіру керек пе? Қолмен өңдеуге оралу үшін «Жоқ» басыңыз.",
                    "The form is wider than the selected A4. Auto-fit column widths before saving? Choose No to return to manual editing.",
                ),
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.Yes,
            )
            if answer != QMessageBox.StandardButton.Yes:
                return
            try:
                fit_form_to_a4(
                    self.editor.form,
                    self.editor.form.preferred_page_orientation,
                )
            except (A4FitError, ValueError) as exc:
                QMessageBox.warning(self, self.windowTitle(), str(exc))
                return
            self._reload_tree()
            self._form_changed()
        try:
            self.editor.form.validate()
            self.repository.save(self.editor.form)
        except (OSError, PermissionError, ValueError) as exc:
            QMessageBox.warning(self, self.windowTitle(), str(exc))
            return
        self.draft.mark_saved()
        self.saved_form = self.draft.saved_copy()
        self.preview_controller.apply(self.editor.form)
        self._update_dirty_state()
