from __future__ import annotations

from pathlib import Path

path = Path("src/geoworkbench/ui/file_workspace_widget.py")
content = path.read_text(encoding="utf-8")
replacements = {
    'pixmap.loadFromData(rendered.payload, b"PNG")': "pixmap.loadFromData(rendered.payload)",
    'pixmap.loadFromData(buffer.getvalue(), b"PNG")': "pixmap.loadFromData(buffer.getvalue())",
}
for old, new in replacements.items():
    count = content.count(old)
    if count != 1:
        raise RuntimeError(f"Expected one occurrence, found {count}: {old}")
    content = content.replace(old, new, 1)
path.write_text(content, encoding="utf-8", newline="\n")
