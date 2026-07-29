from __future__ import annotations

from pathlib import Path


def replace_required(path: str, old: str, new: str) -> None:
    target = Path(path)
    content = target.read_text(encoding="utf-8")
    if old not in content:
        raise RuntimeError(f"Expected fragment not found in {path}: {old!r}")
    target.write_text(content.replace(old, new, 1), encoding="utf-8")


replace_required(
    "src/geoworkbench/files/engineering.py",
    "            operation = _ALLOWED_BINOPS.get(type(node.op))\n            if operation is None:\n",
    "            binary_operation = _ALLOWED_BINOPS.get(type(node.op))\n            if binary_operation is None:\n",
)
replace_required(
    "src/geoworkbench/files/engineering.py",
    "                return float(operation(left, right))\n",
    "                return float(binary_operation(left, right))\n",
)
replace_required(
    "src/geoworkbench/files/engineering.py",
    "            operation = _ALLOWED_UNARYOPS.get(type(node.op))\n            if operation is None:\n",
    "            unary_operation = _ALLOWED_UNARYOPS.get(type(node.op))\n            if unary_operation is None:\n",
)
replace_required(
    "src/geoworkbench/files/engineering.py",
    "            return float(operation(self._evaluate_node(node.operand, depth=depth + 1)))\n",
    "            return float(unary_operation(self._evaluate_node(node.operand, depth=depth + 1)))\n",
)
replace_required(
    "src/geoworkbench/files/engineering.py",
    "def _linear(key: str, label: str, factor: float) -> UnitDefinition:\n    return UnitDefinition(\n        key,\n        label,\n        lambda value, scale=factor: value * scale,\n        lambda value, scale=factor: value / scale,\n    )\n",
    "def _linear(key: str, label: str, factor: float) -> UnitDefinition:\n    def to_base(value: float) -> float:\n        return value * factor\n\n    def from_base(value: float) -> float:\n        return value / factor\n\n    return UnitDefinition(key, label, to_base, from_base)\n",
)
replace_required(
    "src/geoworkbench/files/archive_service.py",
    "        with tarfile.open(output, modes[archive_format]) as archive:\n",
    "        mode: Any = modes[archive_format]\n        with tarfile.open(output, mode) as archive:\n",
)
replace_required(
    "src/geoworkbench/files/archive_service.py",
    "                    information = getattr(archive, \"list\", lambda: [])()\n",
    "                    information: list[Any] = getattr(archive, \"list\", lambda: [])()\n",
)
replace_required(
    "src/geoworkbench/files/logo_service.py",
    "    def _font(size: int) -> ImageFont.ImageFont:\n",
    "    def _font(size: int) -> ImageFont.ImageFont | ImageFont.FreeTypeFont:\n",
)
for line_number in (452, 656):
    path = Path("src/geoworkbench/ui/file_workspace_widget.py")
    content = path.read_text(encoding="utf-8")
    old = 'loadFromData(payload, "PNG")'
    if old not in content:
        raise RuntimeError(f"Expected QPixmap loadFromData call not found before replacement {line_number}")
    path.write_text(content.replace(old, 'loadFromData(payload, b"PNG")', 1), encoding="utf-8")
