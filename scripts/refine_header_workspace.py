from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def replace_once(path: Path, old: str, new: str, label: str) -> None:
    text = path.read_text(encoding="utf-8")
    count = text.count(old)
    if count != 1:
        raise RuntimeError(f"{label}: expected one match, found {count}")
    path.write_text(text.replace(old, new, 1), encoding="utf-8")


importer = ROOT / "src/geoworkbench/importers/skf_importer.py"
replace_once(
    importer,
    '''        if resolved_kind == "frame":
            return MasterlogHeaderElement(
''',
    '''        if resolved_kind == "frame":
            return MasterlogHeaderElement(
''',
    "confirm frame branch",
)
replace_once(
    importer,
    '''        return MasterlogHeaderElement(
            str(uuid4()),
            "line",
            x,
            y,
            shape_width,
            shape_height,
''',
    '''        line_x = x
        line_y = y
        if resolved_kind == "horizontal":
            line_y += max(0.0, (height - shape_height) / 2.0)
        elif resolved_kind == "vertical":
            line_x += max(0.0, (width - shape_width) / 2.0)
        return MasterlogHeaderElement(
            str(uuid4()),
            "line",
            line_x,
            line_y,
            shape_width,
            shape_height,
''',
    "centre normalized SKF line",
)
for old, new, label in (
    ('return "horizontal", max(width, height, 1.0), 0.0', 'return "horizontal", max(width, height, 1.0), 0.1', "explicit horizontal thickness"),
    ('return "vertical", 0.0, max(width, height, 1.0)', 'return "vertical", 0.1, max(width, height, 1.0)', "explicit vertical thickness"),
    ('return "horizontal", max(width, 1.0), 0.0', 'return "horizontal", max(width, 1.0), 0.1', "inferred horizontal thickness"),
    ('return "vertical", 0.0, max(height, 1.0)', 'return "vertical", 0.1, max(height, 1.0)', "inferred vertical thickness"),
):
    replace_once(importer, old, new, label)

header = ROOT / "src/geoworkbench/ui/masterlog_header_dialog.py"
replace_once(
    header,
    '''        moved: Callable[[str, float, float], None],
        activated: Callable[[str], None],
    ) -> None:
        super().__init__(QRectF(0.0, 0.0, element.width_mm, element.height_mm))
        self.element_id = element.element_id
        self._moved = moved
        self._activated = activated
''',
    '''        moved: Callable[[str, float, float], None],
        activated: Callable[[str], None],
        edited: Callable[[], None],
    ) -> None:
        super().__init__(QRectF(0.0, 0.0, element.width_mm, element.height_mm))
        self.element_id = element.element_id
        self._moved = moved
        self._activated = activated
        self._edited = edited
''',
    "rect edit callback",
)
replace_once(
    header,
    '''    def mouseDoubleClickEvent(self, event) -> None:  # noqa: N802 - Qt API
        self._activated(self.element_id)
        super().mouseDoubleClickEvent(event)

    def mouseReleaseEvent(self, event) -> None:  # noqa: N802 - Qt API
''',
    '''    def mouseDoubleClickEvent(self, event) -> None:  # noqa: N802 - Qt API
        self._activated(self.element_id)
        self._edited()
        super().mouseDoubleClickEvent(event)

    def mouseReleaseEvent(self, event) -> None:  # noqa: N802 - Qt API
''',
    "rect double click edit",
)
replace_once(
    header,
    '''        moved: Callable[[str, float, float], None],
        activated: Callable[[str], None],
    ) -> None:
        super().__init__(0.0, 0.0, element.width_mm, element.height_mm)
        self.element_id = element.element_id
        self._moved = moved
        self._activated = activated
''',
    '''        moved: Callable[[str, float, float], None],
        activated: Callable[[str], None],
        edited: Callable[[], None],
    ) -> None:
        super().__init__(0.0, 0.0, element.width_mm, element.height_mm)
        self.element_id = element.element_id
        self._moved = moved
        self._activated = activated
        self._edited = edited
''',
    "line edit callback",
)
# Replace the remaining identical line double-click method after the rectangle method was changed.
replace_once(
    header,
    '''    def mouseDoubleClickEvent(self, event) -> None:  # noqa: N802 - Qt API
        self._activated(self.element_id)
        super().mouseDoubleClickEvent(event)

    def mouseReleaseEvent(self, event) -> None:  # noqa: N802 - Qt API
''',
    '''    def mouseDoubleClickEvent(self, event) -> None:  # noqa: N802 - Qt API
        self._activated(self.element_id)
        self._edited()
        super().mouseDoubleClickEvent(event)

    def mouseReleaseEvent(self, event) -> None:  # noqa: N802 - Qt API
''',
    "line double click edit",
)
replace_once(
    header,
    '''                    self._move_preview_element,
                    self._activate_preview_element,
                )
                line_graphic.setPen''',
    '''                    self._move_preview_element,
                    self._activate_preview_element,
                    self._edit,
                )
                line_graphic.setPen''',
    "pass line edit callback",
)
replace_once(
    header,
    '''                self._move_preview_element,
                self._activate_preview_element,
            )
            rect_graphic.setPen''',
    '''                self._move_preview_element,
                self._activate_preview_element,
                self._edit,
            )
            rect_graphic.setPen''',
    "pass rect edit callback",
)
replace_once(
    header,
    '''        if orientation == "horizontal":
            width = max(10.0, element.width_mm, element.height_mm)
            height = 0.0
        else:
            width = 0.0
            height = max(10.0, element.height_mm, element.width_mm)
''',
    '''        if orientation == "horizontal":
            width = max(10.0, element.width_mm, element.height_mm)
            height = 0.1
        else:
            width = 0.1
            height = max(10.0, element.height_mm, element.width_mm)
''',
    "editable line minimum thickness",
)
