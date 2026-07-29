from __future__ import annotations

from pathlib import Path

path = Path(__file__).resolve().parents[1] / "src/geoworkbench/ui/masterlog_header_dialog.py"
text = path.read_text(encoding="utf-8")
start_marker = "    def _element_tooltip(self, element: MasterlogHeaderElement) -> str:\n"
end_marker = "    def _apply_inspector_geometry(self) -> None:\n"
start = text.find(start_marker)
end = text.find(end_marker, start + len(start_marker))
if start < 0 or end < 0:
    raise RuntimeError("Generated tooltip method boundaries were not found")

replacement = '''    def _element_tooltip(self, element: MasterlogHeaderElement) -> str:
        type_name = {
            "text": "Текст",
            "field": "Автоматическое поле",
            "image": "Изображение / логотип",
            "line": "Линия",
            "lithotype_swatch": "Образец литотипа",
            "lithology_legend": "Литологическая легенда",
            "lba_legend": "Легенда ЛБА",
        }.get(element.element_type, element.element_type)
        newline = chr(10)
        content = self._preview_text(element).replace(newline, " ")
        source = element.properties.get("source_component")
        source_text = (
            f"{newline}Источник SKF: {source}"
            if isinstance(source, str) and source
            else ""
        )
        print_warning = ""
        if (
            element.element_type == "line"
            and element.width_mm > 0.5
            and element.height_mm > 0.5
        ):
            print_warning = f"{newline}Внимание: диагональ будет напечатана как видна."
        return (
            f"{type_name}{newline}Содержимое: {content}{newline}"
            f"X={element.x_mm:g}, Y={element.y_mm:g}, "
            f"размер={element.width_mm:g}×{element.height_mm:g} мм"
            f"{source_text}{print_warning}{newline}"
            "Двойной щелчок — все свойства."
        )

'''
path.write_text(text[:start] + replacement + text[end:], encoding="utf-8")
