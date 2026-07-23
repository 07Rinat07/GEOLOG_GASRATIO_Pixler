from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_physical_print_gate_tool_requires_explicit_print_flag() -> None:
    source = (ROOT / "tools/physical_print_gate.py").read_text()

    assert 'parser.add_argument("--print-test", action="store_true")' in source
    assert "if not args.print_test:" in source
    assert "require_physical_gate=True" in source
    assert "QPrinterInfo.availablePrinterNames" in source
