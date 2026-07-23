from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from PySide6.QtPrintSupport import QPrinter, QPrinterInfo
from PySide6.QtWidgets import QApplication, QLabel

from geoworkbench.printing.page_settings import (
    PrintOrientation,
    PrintPageFormat,
    PrintPageSettings,
)
from geoworkbench.printing.print_job import PrintJobSettings, PrintOutputFormat
from geoworkbench.printing.print_layout import PrintScaleMode
from geoworkbench.services.localization import AppLanguage
from geoworkbench.services.print_jobs import PrintJobExecutor


def main() -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Inspect a Windows printer and optionally send a "
            "two-dimensional continuation test."
        )
    )
    parser.add_argument("--printer", help="Exact printer name. Omit to list available printers.")
    parser.add_argument(
        "--format", choices=("a4", "a3", "custom", "roll"), default="a4"
    )
    parser.add_argument("--orientation", choices=("portrait", "landscape"), default="portrait")
    parser.add_argument("--width-mm", type=float, default=300.0)
    parser.add_argument("--height-mm", type=float, default=1200.0)
    parser.add_argument("--dpi", type=int, default=300)
    parser.add_argument(
        "--scale", choices=("fit", "actual_size"), default="actual_size"
    )
    parser.add_argument("--print-test", action="store_true")
    args = parser.parse_args()

    app = QApplication.instance() or QApplication([])
    del app
    if not args.printer:
        print(json.dumps(QPrinterInfo.availablePrinterNames(), ensure_ascii=False, indent=2))
        return 0

    info = QPrinterInfo.printerInfo(args.printer)
    if info.isNull():
        print(json.dumps({"ok": False, "error": "printer-not-found"}, indent=2))
        return 2

    printer = QPrinter(info, QPrinter.PrinterMode.HighResolution)
    page = PrintPageSettings(
        page_format=PrintPageFormat(args.format),
        orientation=PrintOrientation(args.orientation),
        custom_width_mm=args.width_mm,
        custom_height_mm=args.height_mm,
        scale_mode=PrintScaleMode(args.scale),
        continuation_overlap_mm=5.0,
    )
    job = PrintJobSettings(
        output_format=PrintOutputFormat.PRINTER,
        page=page,
        dpi=args.dpi,
    )
    label = QLabel(
        "GEOLOG GASRATIO@Pixler physical printer gate\n"
        "A4 / A3 / custom / roll · Fit / 100% · continuation 1…N\n"
        "Русский · Қазақша · English · ΔP · µg/L · Ω · ρ"
    )
    label.resize(2200 if page.scale_mode is PrintScaleMode.ACTUAL_SIZE else 900, 620)
    executor = PrintJobExecutor()
    gate = executor.physical_printer_gate(printer, label, job)
    payload = {
        "ok": gate.ok,
        "printer": gate.printer_name,
        "selected_dpi": gate.selected_dpi,
        "page_count": gate.page_count,
        "issues": [
            {"code": item.code, "severity": item.severity.value, "message": item.message}
            for item in gate.issues
        ],
    }
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    if not gate.ok:
        return 3
    if not args.print_test:
        return 0

    result = executor.render_to_printer(
        label,
        printer,
        job,
        source_name="Physical printer gate",
        language=AppLanguage.EN,
        require_physical_gate=True,
    )
    print(
        json.dumps(
            {
                "printed": True,
                "page_count": result.page_count,
                "printer": gate.printer_name,
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
