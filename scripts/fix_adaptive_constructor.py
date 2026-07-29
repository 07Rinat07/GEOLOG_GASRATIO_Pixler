from __future__ import annotations

from pathlib import Path

path = Path(__file__).resolve().parents[1] / "src/geoworkbench/ui/constructor_dialog.py"
text = path.read_text(encoding="utf-8")
needle = "        right.addWidget(self.print_toolbar)\n        )\n"
count = text.count(needle)
if count != 1:
    raise RuntimeError(
        f"constructor toolbar cleanup: expected one dangling parenthesis, found {count}"
    )
path.write_text(text.replace(needle, "        right.addWidget(self.print_toolbar)\n", 1), encoding="utf-8")
