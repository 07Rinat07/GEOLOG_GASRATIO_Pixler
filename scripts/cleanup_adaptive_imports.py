from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

changes = {
    "src/geoworkbench/ui/constructor_dialog.py": (
        "from geoworkbench.ui.collapsible_section import CollapsibleSection\n",
        "",
    ),
    "src/geoworkbench/ui/masterlog_header_dialog.py": (
        "    QStyle,\n",
        "",
    ),
}

for relative_path, (old, new) in changes.items():
    path = ROOT / relative_path
    text = path.read_text(encoding="utf-8")
    count = text.count(old)
    if count != 1:
        raise RuntimeError(f"{relative_path}: expected one cleanup target, found {count}")
    path.write_text(text.replace(old, new, 1), encoding="utf-8")
