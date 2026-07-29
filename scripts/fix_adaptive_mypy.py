from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

preview_path = ROOT / "src/geoworkbench/ui/tablet_track_preview_widget.py"
preview = preview_path.read_text(encoding="utf-8")
replacements = (
    (
        "from PySide6.QtCore import QRectF, QSize, Qt\n",
        "from PySide6.QtCore import QLineF, QRectF, QSize, Qt\n",
    ),
    (
        "            style = self._track.curve_style(mnemonic) if mnemonic else CurveStyle()\n",
        "            style = (\n"
        "                self._track.curve_style(mnemonic) or CurveStyle()\n"
        "                if mnemonic\n"
        "                else CurveStyle()\n"
        "            )\n",
    ),
    (
        "                painter.drawLine(row.left() + 4, row.bottom() - 2, row.right() - 4, row.bottom() - 2)\n",
        "                painter.drawLine(\n"
        "                    QLineF(\n"
        "                        row.left() + 4,\n"
        "                        row.bottom() - 2,\n"
        "                        row.right() - 4,\n"
        "                        row.bottom() - 2,\n"
        "                    )\n"
        "                )\n",
    ),
    (
        "                painter.drawLine(x, body.top(), x, body.bottom())\n",
        "                painter.drawLine(QLineF(x, body.top(), x, body.bottom()))\n",
    ),
    (
        "                painter.drawLine(body.left(), y, body.right(), y)\n",
        "                painter.drawLine(QLineF(body.left(), y, body.right(), y))\n",
    ),
)
for old, new in replacements:
    count = preview.count(old)
    expected = 2 if old == "                painter.drawLine(x, body.top(), x, body.bottom())\n" else 1
    if count != expected:
        raise RuntimeError(f"preview replacement expected {expected}, found {count}: {old!r}")
    preview = preview.replace(old, new)
preview_path.write_text(preview, encoding="utf-8")

editor_path = ROOT / "src/geoworkbench/ui/tablet_track_editor_dialog.py"
editor = editor_path.read_text(encoding="utf-8")
old_block = '''    def _connect_preview_signals(self) -> None:
        for control in (
            self.title_input,
            self.group_input,
            self.axis_input,
            self.caption_input,
            self.color_input,
            self.header_text_color_input,
            self.header_line_color_input,
        ):
            control.textChanged.connect(self._refresh_preview)
        for control in (
            self.title_orientation_input,
            self.title_position_input,
            self.style_input,
            self.scale_input,
            self.auto_range_input,
        ):
            control.currentIndexChanged.connect(self._refresh_preview)
        for control in (
            self.width_input,
            self.grid_major_input,
            self.grid_minor_input,
            self.grid_alpha_input,
            self.line_width_input,
            self.min_input,
            self.max_input,
        ):
            control.valueChanged.connect(self._refresh_preview)
        for control in (
            self.show_interval_labels_input,
            self.grid_x_input,
            self.grid_y_input,
            self.grid_print_input,
        ):
            control.toggled.connect(self._refresh_preview)
'''
new_block = '''    def _connect_preview_signals(self) -> None:
        for line_edit in (
            self.title_input,
            self.group_input,
            self.axis_input,
            self.caption_input,
            self.color_input,
            self.header_text_color_input,
            self.header_line_color_input,
        ):
            line_edit.textChanged.connect(self._refresh_preview)
        for combo_box in (
            self.title_orientation_input,
            self.title_position_input,
            self.style_input,
            self.scale_input,
            self.auto_range_input,
        ):
            combo_box.currentIndexChanged.connect(self._refresh_preview)
        for spin_box in (
            self.width_input,
            self.grid_major_input,
            self.grid_minor_input,
            self.grid_alpha_input,
            self.line_width_input,
            self.min_input,
            self.max_input,
        ):
            spin_box.valueChanged.connect(self._refresh_preview)
        for check_box in (
            self.show_interval_labels_input,
            self.grid_x_input,
            self.grid_y_input,
            self.grid_print_input,
        ):
            check_box.toggled.connect(self._refresh_preview)
'''
count = editor.count(old_block)
if count != 1:
    raise RuntimeError(f"editor signal block expected once, found {count}")
editor_path.write_text(editor.replace(old_block, new_block, 1), encoding="utf-8")
