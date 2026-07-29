from __future__ import annotations

from pathlib import Path

path = Path(__file__).resolve().parent / "refine_header_workspace.py"
text = path.read_text(encoding="utf-8")
old = '''    count = text.count(old)
    if count != 1:
        raise RuntimeError(f"{label}: expected one match, found {count}")
    path.write_text(text.replace(old, new, 1), encoding="utf-8")
'''
new = '''    count = text.count(old)
    expected = 2 if label == "rect double click edit" else 1
    if count != expected:
        raise RuntimeError(f"{label}: expected {expected} match(es), found {count}")
    path.write_text(text.replace(old, new, 1), encoding="utf-8")
'''
if text.count(old) != 1:
    raise RuntimeError("refinement applicator helper was not found exactly once")
path.write_text(text.replace(old, new, 1), encoding="utf-8")
