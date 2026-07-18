from __future__ import annotations

from collections.abc import Callable

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QComboBox,
    QCheckBox,
    QDialog,
    QDialogButtonBox,
    QDoubleSpinBox,
    QFormLayout,
    QHBoxLayout,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QMessageBox,
    QPushButton,
    QVBoxLayout,
)

from geoworkbench.domain.models import (
    Dataset,
    MasterlogColumnTemplate,
    MasterlogCurveStyle,
    MasterlogTemplate,
)
from geoworkbench.project.masterlog_template_controller import MasterlogTemplateController
from geoworkbench.services.localization import AppLanguage, Localizer


class ColumnPropertiesDialog(QDialog):
    def __init__(
        self,
        parent=None,
        *,
        column: MasterlogColumnTemplate | None = None,
        dataset: Dataset | None = None,
        language: AppLanguage = AppLanguage.RU,
    ) -> None:
        super().__init__(parent)
        localizer = Localizer.create(language)
        self.setWindowTitle(localizer.text("masterlog_columns.properties"))
        self.title_input = QLineEdit(column.title if column else "")
        self.type_input = QComboBox()
        self.type_input.setEditable(True)
        self.type_input.addItems(
            [
                "curves",
                "depth",
                "stratigraphy",
                "lithology",
                "cuttings",
                "calcimetry",
                "lba",
                "text",
                "cuttings_description",
                "analysis_interpretation",
            ]
        )
        if column:
            self.type_input.setCurrentText(column.column_type)
        self.width_input = QDoubleSpinBox()
        self.width_input.setRange(5.0, 200.0)
        self.width_input.setSuffix(" mm")
        self.width_input.setValue(column.width_mm if column else 30.0)
        self.curves_input = QLineEdit(", ".join(column.curve_mnemonics) if column else "")
        self._curve_styles = dict(column.curve_styles) if column else {}
        self.curves_input.setObjectName("masterlog-column-curves")
        curves_row = QHBoxLayout()
        curves_row.addWidget(self.curves_input)
        self.choose_curves_button = QPushButton(
            {
                AppLanguage.RU: "Выбрать из LAS...",
                AppLanguage.KK: "LAS-тан таңдау...",
                AppLanguage.EN: "Choose from LAS...",
            }[language]
        )
        self.choose_curves_button.setEnabled(dataset is not None and bool(dataset.curves))
        self.choose_curves_button.clicked.connect(
            lambda: self._choose_dataset_curves(dataset, language)
        )
        curves_row.addWidget(self.choose_curves_button)
        self.curve_styles_button = QPushButton(
            {
                AppLanguage.RU: "Стили кривых...",
                AppLanguage.KK: "Қисық стильдері...",
                AppLanguage.EN: "Curve styles...",
            }[language]
        )
        self.curve_styles_button.clicked.connect(lambda: self._edit_curve_styles(language))
        self.curves_input.textChanged.connect(self._update_curve_styles_enabled)
        curves_row.addWidget(self.curve_styles_button)
        self.scale_input = QComboBox()
        self.scale_input.addItem(localizer.text("inspector.linear"), "linear")
        self.scale_input.addItem(localizer.text("inspector.logarithmic"), "logarithmic")
        self.scale_input.setCurrentIndex(
            self.scale_input.findData(column.x_scale if column else "linear")
        )
        self.auto_range_input = QCheckBox(localizer.text("common.auto"))
        self.auto_range_input.setChecked(
            column is None or column.x_min is None or column.x_max is None
        )
        self.minimum_input = QDoubleSpinBox()
        self.maximum_input = QDoubleSpinBox()
        for control in (self.minimum_input, self.maximum_input):
            control.setRange(-1e12, 1e12)
            control.setDecimals(6)
        self.minimum_input.setValue(column.x_min if column and column.x_min is not None else 0.1)
        self.maximum_input.setValue(column.x_max if column and column.x_max is not None else 100.0)
        self.legend_input = QCheckBox(localizer.text("masterlog_columns.show_legend"))
        self.legend_input.setChecked(column.show_legend if column else True)
        self.color_input = QLineEdit(column.line_color if column else "#2563eb")
        self.line_width_input = QDoubleSpinBox()
        self.line_width_input.setRange(0.5, 10.0)
        self.line_width_input.setDecimals(1)
        self.line_width_input.setValue(column.line_width if column else 1.5)
        self.line_style_input = QComboBox()
        for value in ("solid", "dash", "dot", "dash_dot"):
            self.line_style_input.addItem(localizer.text(f"inspector.line_style.{value}"), value)
        self.line_style_input.setCurrentIndex(
            self.line_style_input.findData(column.line_style if column else "solid")
        )
        self.auto_range_input.toggled.connect(self._update_range_enabled)
        layout = QFormLayout(self)
        layout.addRow(localizer.text("masterlog_columns.name"), self.title_input)
        layout.addRow(localizer.text("inspector.type"), self.type_input)
        layout.addRow(localizer.text("inspector.width"), self.width_input)
        layout.addRow(localizer.text("inspector.curves"), curves_row)
        layout.addRow(localizer.text("inspector.x_scale"), self.scale_input)
        layout.addRow(self.auto_range_input)
        layout.addRow(localizer.text("inspector.x_minimum"), self.minimum_input)
        layout.addRow(localizer.text("inspector.x_maximum"), self.maximum_input)
        layout.addRow(self.legend_input)
        layout.addRow(localizer.text("inspector.color"), self.color_input)
        layout.addRow(localizer.text("inspector.line_width"), self.line_width_input)
        layout.addRow(localizer.text("inspector.line_style"), self.line_style_input)
        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addRow(buttons)
        self._update_range_enabled(self.auto_range_input.isChecked())
        self._update_curve_styles_enabled()

    def values(
        self,
    ) -> tuple[
        str,
        str,
        float,
        list[str],
        str,
        float | None,
        float | None,
        bool,
        str,
        float,
        str,
    ]:
        curves = [value.strip() for value in self.curves_input.text().split(",")]
        automatic = self.auto_range_input.isChecked()
        return (
            self.title_input.text(),
            self.type_input.currentText(),
            self.width_input.value(),
            [value for value in curves if value],
            str(self.scale_input.currentData()),
            None if automatic else self.minimum_input.value(),
            None if automatic else self.maximum_input.value(),
            self.legend_input.isChecked(),
            self.color_input.text().strip(),
            self.line_width_input.value(),
            str(self.line_style_input.currentData()),
        )

    def _update_range_enabled(self, automatic: bool) -> None:
        self.minimum_input.setEnabled(not automatic)
        self.maximum_input.setEnabled(not automatic)

    def _choose_dataset_curves(self, dataset: Dataset | None, language: AppLanguage) -> None:
        if dataset is None:
            return
        current = [value.strip() for value in self.curves_input.text().split(",") if value.strip()]
        available = sorted(
            (curve.metadata.original_mnemonic for curve in dataset.curves.values()),
            key=str.casefold,
        )
        dialog = DatasetCurveSelectionDialog(current, available, self, language=language)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            self.curves_input.setText(", ".join(dialog.selected_mnemonics()))

    def curve_styles(self) -> dict[str, MasterlogCurveStyle]:
        selected = {value.strip() for value in self.curves_input.text().split(",") if value.strip()}
        return {
            mnemonic: style
            for mnemonic, style in self._curve_styles.items()
            if mnemonic in selected
        }

    def _edit_curve_styles(self, language: AppLanguage) -> None:
        mnemonics = [
            value.strip() for value in self.curves_input.text().split(",") if value.strip()
        ]
        if not mnemonics:
            return
        dialog = CurveStylesDialog(
            mnemonics,
            self._curve_styles,
            self,
            language=language,
            x_scale=str(self.scale_input.currentData()),
            default_color=self.color_input.text().strip(),
            default_width=self.line_width_input.value(),
            default_line_style=str(self.line_style_input.currentData()),
        )
        if dialog.exec() == QDialog.DialogCode.Accepted:
            self._curve_styles = dialog.styles()

    def _update_curve_styles_enabled(self) -> None:
        self.curve_styles_button.setEnabled(
            any(value.strip() for value in self.curves_input.text().split(","))
        )


class CurveStylePropertiesDialog(QDialog):
    def __init__(
        self,
        mnemonic: str,
        style: MasterlogCurveStyle,
        parent=None,
        *,
        language: AppLanguage = AppLanguage.RU,
        x_scale: str = "linear",
    ) -> None:
        super().__init__(parent)
        self.language = language
        self.x_scale = x_scale
        self._result = style
        self.setWindowTitle(
            {
                AppLanguage.RU: f"Кривая {mnemonic}",
                AppLanguage.KK: f"{mnemonic} қисығы",
                AppLanguage.EN: f"Curve {mnemonic}",
            }[language]
        )
        self.color_input = QLineEdit(style.color)
        self.width_input = QDoubleSpinBox()
        self.width_input.setRange(0.5, 10.0)
        self.width_input.setDecimals(1)
        self.width_input.setValue(style.width)
        self.line_style_input = QComboBox()
        for value in ("solid", "dash", "dot", "dash_dot"):
            self.line_style_input.addItem(value, value)
        self.line_style_input.setCurrentIndex(self.line_style_input.findData(style.line_style))
        self.auto_range_input = QCheckBox(
            {
                AppLanguage.RU: "Диапазон колонки / авто",
                AppLanguage.KK: "Баған аралығы / авто",
                AppLanguage.EN: "Column range / auto",
            }[language]
        )
        self.auto_range_input.setChecked(style.x_min is None)
        self.minimum_input = QDoubleSpinBox()
        self.maximum_input = QDoubleSpinBox()
        for control in (self.minimum_input, self.maximum_input):
            control.setRange(-1e12, 1e12)
            control.setDecimals(6)
        self.minimum_input.setValue(style.x_min if style.x_min is not None else 0.0)
        self.maximum_input.setValue(style.x_max if style.x_max is not None else 100.0)
        self.auto_range_input.toggled.connect(self._update_range_enabled)
        form = QFormLayout(self)
        form.addRow("Цвет / Color", self.color_input)
        form.addRow("Толщина / Width", self.width_input)
        form.addRow("Стиль / Style", self.line_style_input)
        form.addRow(self.auto_range_input)
        form.addRow("Minimum X", self.minimum_input)
        form.addRow("Maximum X", self.maximum_input)
        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        form.addRow(buttons)
        self._update_range_enabled(self.auto_range_input.isChecked())

    def accept(self) -> None:
        automatic = self.auto_range_input.isChecked()
        try:
            style = MasterlogCurveStyle(
                self.color_input.text().strip(),
                self.width_input.value(),
                str(self.line_style_input.currentData()),
                None if automatic else self.minimum_input.value(),
                None if automatic else self.maximum_input.value(),
            )
            if self.x_scale == "logarithmic" and style.x_min is not None and style.x_min <= 0:
                raise ValueError(
                    {
                        AppLanguage.RU: "Минимум логарифмической кривой должен быть больше 0",
                        AppLanguage.KK: "Логарифмдік қисықтың минимумы 0-ден үлкен болуы керек",
                        AppLanguage.EN: "A logarithmic curve minimum must be greater than 0",
                    }[self.language]
                )
        except ValueError as exc:
            QMessageBox.warning(self, self.windowTitle(), str(exc))
            return
        self._result = style
        super().accept()

    def result_style(self) -> MasterlogCurveStyle:
        return self._result

    def _update_range_enabled(self, automatic: bool) -> None:
        self.minimum_input.setEnabled(not automatic)
        self.maximum_input.setEnabled(not automatic)


class CurveStylesDialog(QDialog):
    _PALETTE = ("#2563eb", "#dc2626", "#16a34a", "#9333ea", "#ea580c", "#0891b2")

    def __init__(
        self,
        mnemonics: list[str],
        styles: dict[str, MasterlogCurveStyle],
        parent=None,
        *,
        language: AppLanguage = AppLanguage.RU,
        x_scale: str = "linear",
        default_color: str = "#2563eb",
        default_width: float = 1.5,
        default_line_style: str = "solid",
    ) -> None:
        super().__init__(parent)
        self.language = language
        self.x_scale = x_scale
        self.mnemonics = list(dict.fromkeys(mnemonics))
        self._styles = {
            mnemonic: styles.get(
                mnemonic,
                MasterlogCurveStyle(
                    default_color if index == 0 else self._PALETTE[index % len(self._PALETTE)],
                    default_width,
                    default_line_style,
                ),
            )
            for index, mnemonic in enumerate(self.mnemonics)
        }
        self.setWindowTitle(
            {
                AppLanguage.RU: "Стили кривых колонки",
                AppLanguage.KK: "Баған қисықтарының стильдері",
                AppLanguage.EN: "Column curve styles",
            }[language]
        )
        self.list = QListWidget()
        self.list.itemDoubleClicked.connect(lambda _item: self._edit())
        edit_button = QPushButton(
            {AppLanguage.RU: "Изменить", AppLanguage.KK: "Өзгерту", AppLanguage.EN: "Edit"}[
                language
            ]
        )
        edit_button.clicked.connect(self._edit)
        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout = QVBoxLayout(self)
        layout.addWidget(self.list)
        layout.addWidget(edit_button)
        layout.addWidget(buttons)
        self._refresh()
        self.resize(520, 380)

    def styles(self) -> dict[str, MasterlogCurveStyle]:
        return dict(self._styles)

    def _refresh(self) -> None:
        current = self.list.currentRow()
        self.list.clear()
        for mnemonic in self.mnemonics:
            style = self._styles[mnemonic]
            value_range = "auto" if style.x_min is None else f"{style.x_min:g}–{style.x_max:g}"
            self.list.addItem(
                f"{mnemonic} | {style.color} | {style.width:g} px | "
                f"{style.line_style} | X {value_range}"
            )
        if self.list.count():
            self.list.setCurrentRow(max(0, min(current, self.list.count() - 1)))

    def _edit(self) -> None:
        row = self.list.currentRow()
        if row < 0:
            return
        mnemonic = self.mnemonics[row]
        dialog = CurveStylePropertiesDialog(
            mnemonic,
            self._styles[mnemonic],
            self,
            language=self.language,
            x_scale=self.x_scale,
        )
        if dialog.exec() == QDialog.DialogCode.Accepted:
            self._styles[mnemonic] = dialog.result_style()
            self._refresh()


class DatasetCurveSelectionDialog(QDialog):
    def __init__(
        self,
        selected: list[str],
        available: list[str],
        parent=None,
        *,
        language: AppLanguage = AppLanguage.RU,
    ) -> None:
        super().__init__(parent)
        self.setWindowTitle(
            {
                AppLanguage.RU: "Параметры колонки",
                AppLanguage.KK: "Баған параметрлері",
                AppLanguage.EN: "Column parameters",
            }[language]
        )
        self.list = QListWidget()
        self.list.setObjectName("masterlog-dataset-curves")
        ordered = list(dict.fromkeys([*selected, *available]))
        selected_keys = {value.casefold() for value in selected}
        for mnemonic in ordered:
            item = QListWidgetItem(mnemonic)
            item.setFlags(item.flags() | Qt.ItemFlag.ItemIsUserCheckable)
            item.setCheckState(
                Qt.CheckState.Checked
                if mnemonic.casefold() in selected_keys
                else Qt.CheckState.Unchecked
            )
            self.list.addItem(item)
        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout = QVBoxLayout(self)
        layout.addWidget(self.list)
        layout.addWidget(buttons)
        self.resize(360, 440)

    def selected_mnemonics(self) -> list[str]:
        return [
            self.list.item(index).text()
            for index in range(self.list.count())
            if self.list.item(index).checkState() == Qt.CheckState.Checked
        ]


class MasterlogColumnsDialog(QDialog):
    def __init__(
        self,
        controller: MasterlogTemplateController,
        template_id: str,
        parent=None,
        *,
        language: AppLanguage = AppLanguage.RU,
    ) -> None:
        super().__init__(parent)
        self.controller = controller
        self.template_id = template_id
        self.localizer = Localizer.create(language)
        self.setWindowTitle(self.localizer.text("masterlog_columns.title"))
        self.resize(680, 420)
        self.list = QListWidget()
        buttons = QHBoxLayout()
        for text, handler in (
            (self.localizer.text("common.create"), self._add),
            (self.localizer.text("common.edit"), self._edit),
            ("←", lambda: self._move(-1)),
            ("→", lambda: self._move(1)),
            (self.localizer.text("common.delete"), self._remove),
        ):
            button = QPushButton(text)
            button.clicked.connect(handler)
            buttons.addWidget(button)
        layout = QVBoxLayout(self)
        layout.addWidget(self.list)
        layout.addLayout(buttons)
        self.refresh()

    @property
    def template(self) -> MasterlogTemplate:
        return self.controller.session.project.masterlog_templates[self.template_id]

    def refresh(self) -> None:
        self.list.clear()
        for column in self.template.columns:
            curves = ", ".join(column.curve_mnemonics) or "—"
            item = QListWidgetItem(
                f"{column.title} | {column.column_type} | {column.width_mm:g} mm | {curves}"
            )
            item.setData(Qt.ItemDataRole.UserRole, column.column_id)
            self.list.addItem(item)

    def _selected_column(self) -> MasterlogColumnTemplate | None:
        item = self.list.currentItem()
        if item is None:
            QMessageBox.information(self, self.windowTitle(), "Выберите колонку")
            return None
        column_id = str(item.data(Qt.ItemDataRole.UserRole))
        return next(column for column in self.template.columns if column.column_id == column_id)

    def _add(self) -> None:
        dialog = ColumnPropertiesDialog(
            self,
            dataset=self.controller.session.current_dataset,
            language=self.localizer.language,
        )
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return
        (
            title,
            column_type,
            width,
            curves,
            scale,
            x_min,
            x_max,
            legend,
            color,
            line_width,
            line_style,
        ) = dialog.values()
        self._run(
            lambda: self.controller.add_column(
                self.template_id,
                title=title,
                column_type=column_type,
                width_mm=width,
                curve_mnemonics=curves,
                x_scale=scale,
                x_min=x_min,
                x_max=x_max,
                show_legend=legend,
                line_color=color,
                line_width=line_width,
                line_style=line_style,
                curve_styles=dialog.curve_styles(),
            )
        )

    def _edit(self) -> None:
        column = self._selected_column()
        if column is None:
            return
        if edit_masterlog_column(
            self,
            self.controller,
            self.template_id,
            column.column_id,
            language=self.localizer.language,
        ):
            self.refresh()

    def _remove(self) -> None:
        column = self._selected_column()
        if column is not None:
            self._run(lambda: self.controller.remove_column(self.template_id, column.column_id))

    def _move(self, offset: int) -> None:
        column = self._selected_column()
        if column is not None:
            self._run(
                lambda: self.controller.move_column(self.template_id, column.column_id, offset)
            )

    def _run(self, operation: Callable[[], object]) -> None:
        try:
            operation()
        except (KeyError, ValueError) as exc:
            QMessageBox.warning(self, self.windowTitle(), str(exc))
        self.refresh()


def edit_masterlog_column(
    parent,
    controller: MasterlogTemplateController,
    template_id: str,
    column_id: str,
    *,
    language: AppLanguage = AppLanguage.RU,
) -> bool:
    template = controller.session.project.masterlog_templates[template_id]
    column = next(item for item in template.columns if item.column_id == column_id)
    dialog = ColumnPropertiesDialog(
        parent,
        column=column,
        dataset=controller.session.current_dataset,
        language=language,
    )
    if dialog.exec() != QDialog.DialogCode.Accepted:
        return False
    (
        title,
        column_type,
        width,
        curves,
        scale,
        x_min,
        x_max,
        legend,
        color,
        line_width,
        line_style,
    ) = dialog.values()
    controller.update_column(
        template_id,
        column_id,
        title=title,
        column_type=column_type,
        width_mm=width,
        curve_mnemonics=curves,
        x_scale=scale,
        x_min=x_min,
        x_max=x_max,
        show_legend=legend,
        line_color=color,
        line_width=line_width,
        line_style=line_style,
        curve_styles=dialog.curve_styles(),
    )
    return True
