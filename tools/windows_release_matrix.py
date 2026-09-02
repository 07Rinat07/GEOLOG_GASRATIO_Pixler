#!/usr/bin/env python3
"""Run the automated Windows GUI/HiDPI/PDF release acceptance matrix.

The command writes generated evidence only below ``build/ci-artifacts`` (or an
explicit output directory). A physical printer can be included by an operator,
but a successful physical result requires an explicit print and structured
visual confirmation; CI therefore records that part as pending instead of
claiming it.
"""

from __future__ import annotations

import argparse
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
import hashlib
import json
import os
from pathlib import Path
import platform
import sys
import time
from typing import Any, Iterable

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
DEFAULT_OUTPUT = ROOT / "build" / "ci-artifacts" / "windows-acceptance"
CHECKLIST_SCHEMA = "geolog.windows-release-checklist.v2"
PHYSICAL_EVIDENCE_SCHEMA = "geolog.physical-printer-evidence.v1"
SUPPORTED_SCALE_FACTORS = (1.0, 1.25, 1.5, 2.0)

PHYSICAL_EVIDENCE_OPTIONS = (
    (
        "long_rich_text_readable",
        "--confirm-rich-text",
        "Confirm that the long INTERPRETATION rich text is complete and readable.",
    ),
    (
        "embedded_cuttings_photo_readable",
        "--confirm-cuttings-photo",
        "Confirm that the embedded cuttings-style photo is present and readable.",
    ),
    (
        "custom_heading_correct",
        "--confirm-custom-heading",
        "Confirm that the custom printed heading is correct.",
    ),
    (
        "interval_bounds_correct",
        "--confirm-interval-bounds",
        "Confirm that interpretation interval boundaries are visible and correct.",
    ),
    (
        "color_reproduction_acceptable",
        "--confirm-color",
        "Confirm that color swatches and colored content are distinguishable on paper.",
    ),
    (
        "driver_margins_acceptable",
        "--confirm-driver-margins",
        "Confirm that physical driver margins do not clip required content.",
    ),
    (
        "driver_warnings_absent",
        "--confirm-no-driver-warning",
        "Confirm that the printer driver produced no paper/margin/scaling warning.",
    ),
)
PHYSICAL_EVIDENCE_FIELDS = tuple(item[0] for item in PHYSICAL_EVIDENCE_OPTIONS)
CUT03_REQUIRED_CASES = {
    "physical-a4-portrait-fit": ("a4", "portrait"),
    "physical-a3-landscape-actual-size": ("a3", "landscape"),
}


@dataclass(frozen=True, slots=True)
class MatrixCase:
    case_id: str
    page_format: str
    orientation: str
    scale_mode: str
    dpi: int
    widget_width: int
    widget_height: int
    expected_min_pages: int = 1
    custom_width_mm: float = 210.0
    custom_height_mm: float = 297.0
    language: str = "en"
    widget_kind: str = "label"
    pagination_mode: str = "current"
    units_per_page: float = 50.0


@dataclass(frozen=True, slots=True)
class CaseResult:
    case_id: str
    status: str
    page_count: int
    pdf_path: str
    screenshot_path: str
    pdf_sha256: str
    pdf_size_bytes: int
    page_sizes_points: tuple[tuple[float, float], ...]
    error: str | None = None


AUTOMATED_CASES = (
    MatrixCase(
        case_id="tablet-full-range-a4-fit",
        page_format="a4",
        orientation="portrait",
        scale_mode="fit",
        dpi=96,
        widget_width=900,
        widget_height=620,
        expected_min_pages=4,
        language="ru",
        widget_kind="tablet",
        pagination_mode="full",
        units_per_page=50.0,
    ),
    MatrixCase(
        case_id="a4-portrait-fit",
        page_format="a4",
        orientation="portrait",
        scale_mode="fit",
        dpi=96,
        widget_width=900,
        widget_height=620,
        language="ru",
    ),
    MatrixCase(
        case_id="a3-landscape-fit",
        page_format="a3",
        orientation="landscape",
        scale_mode="fit",
        dpi=150,
        widget_width=1400,
        widget_height=720,
        language="kk",
    ),
    MatrixCase(
        case_id="a4-landscape-actual-size-continuation",
        page_format="a4",
        orientation="landscape",
        scale_mode="actual_size",
        dpi=300,
        widget_width=8000,
        widget_height=720,
        expected_min_pages=2,
        language="en",
    ),
    MatrixCase(
        case_id="roll-actual-size",
        page_format="roll",
        orientation="portrait",
        scale_mode="actual_size",
        dpi=300,
        widget_width=1800,
        widget_height=1400,
        custom_width_mm=300.0,
        custom_height_mm=1200.0,
        language="ru",
    ),
)

PHYSICAL_CASES = (
    MatrixCase(
        case_id="physical-a4-portrait-fit",
        page_format="a4",
        orientation="portrait",
        scale_mode="fit",
        dpi=300,
        widget_width=900,
        widget_height=620,
    ),
    MatrixCase(
        case_id="physical-a3-landscape-actual-size",
        page_format="a3",
        orientation="landscape",
        scale_mode="actual_size",
        dpi=300,
        widget_width=1800,
        widget_height=720,
        expected_min_pages=2,
    ),
    MatrixCase(
        case_id="physical-custom-fit",
        page_format="custom",
        orientation="portrait",
        scale_mode="fit",
        dpi=300,
        widget_width=1200,
        widget_height=900,
        custom_width_mm=300.0,
        custom_height_mm=600.0,
    ),
    MatrixCase(
        case_id="physical-roll-continuation",
        page_format="roll",
        orientation="portrait",
        scale_mode="actual_size",
        dpi=300,
        widget_width=2400,
        widget_height=1600,
        expected_min_pages=2,
        custom_width_mm=300.0,
        custom_height_mm=1200.0,
    ),
)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Run Windows GUI/HiDPI/PDF acceptance and write a JSON checklist."
    )
    parser.add_argument(
        "--scale-factor",
        type=float,
        default=1.0,
        choices=SUPPORTED_SCALE_FACTORS,
        help="Qt scale factor. Run each value in a separate process.",
    )
    parser.add_argument(
        "--platform",
        choices=("windows", "offscreen"),
        default="windows" if sys.platform == "win32" else "offscreen",
        help="Qt platform plugin used by the acceptance process.",
    )
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--printer", help="Exact physical printer name.")
    parser.add_argument("--operator", help="Operator who checked the physical output.")
    parser.add_argument(
        "--print-test",
        action="store_true",
        help="Send all physical acceptance cases to the selected printer.",
    )
    parser.add_argument(
        "--confirm-physical-output",
        action="store_true",
        help="Finalize physical acceptance after all structured evidence checks are confirmed.",
    )
    for field, flag, help_text in PHYSICAL_EVIDENCE_OPTIONS:
        parser.add_argument(flag, dest=field, action="store_true", help=help_text)
    parser.add_argument(
        "--physical-notes",
        default="",
        help="Short operator notes stored in the generated checklist.",
    )
    parser.add_argument(
        "--require-physical",
        action="store_true",
        help="Return a failure unless the physical printer result has complete evidence.",
    )
    return parser


def physical_evidence_from_args(args: argparse.Namespace) -> dict[str, bool]:
    return {field: bool(getattr(args, field, False)) for field in PHYSICAL_EVIDENCE_FIELDS}


def physical_evidence_complete(evidence: dict[str, Any]) -> bool:
    return all(evidence.get(field) is True for field in PHYSICAL_EVIDENCE_FIELDS)


def validate_physical_payload(physical: dict[str, Any]) -> bool:
    """Fail closed unless a passed payload contains complete paper evidence."""

    if physical.get("status") != "passed":
        return False
    if physical.get("printed") is not True or physical.get("visually_confirmed") is not True:
        return False
    if not str(physical.get("printer", "")).strip() or not str(physical.get("operator", "")).strip():
        return False
    if physical.get("evidence_schema") != PHYSICAL_EVIDENCE_SCHEMA:
        return False
    evidence = physical.get("evidence")
    if not isinstance(evidence, dict) or not physical_evidence_complete(evidence):
        return False

    raw_cases = physical.get("cases")
    if not isinstance(raw_cases, list):
        return False
    by_id = {
        str(item.get("case_id")): item
        for item in raw_cases
        if isinstance(item, dict) and item.get("case_id")
    }
    for case in PHYSICAL_CASES:
        result = by_id.get(case.case_id)
        if result is None:
            return False
        if result.get("gate_ok") is not True or result.get("printed") is not True:
            return False
        if result.get("page_format") != case.page_format:
            return False
        if result.get("orientation") != case.orientation:
            return False
        if int(result.get("page_count", 0)) < case.expected_min_pages:
            return False
    for case_id, (page_format, orientation) in CUT03_REQUIRED_CASES.items():
        result = by_id.get(case_id)
        if result is None:
            return False
        if result.get("page_format") != page_format or result.get("orientation") != orientation:
            return False
    return True


def validate_physical_arguments(args: argparse.Namespace) -> None:
    if args.print_test and not args.printer:
        raise ValueError("--print-test requires --printer")

    evidence = physical_evidence_from_args(args)
    if any(evidence.values()) and not args.confirm_physical_output:
        raise ValueError(
            "structured physical evidence flags require --confirm-physical-output"
        )
    if args.confirm_physical_output:
        missing = [
            option
            for option, value in (
                ("--printer", args.printer),
                ("--operator", args.operator),
                ("--print-test", args.print_test),
            )
            if not value
        ]
        missing.extend(
            flag
            for field, flag, _ in PHYSICAL_EVIDENCE_OPTIONS
            if evidence.get(field) is not True
        )
        if missing:
            raise ValueError(
                "--confirm-physical-output requires " + ", ".join(missing)
            )


def configure_qt_environment(scale_factor: float, platform_name: str) -> None:
    os.environ["QT_SCALE_FACTOR"] = _format_scale(scale_factor)
    os.environ["QT_QPA_PLATFORM"] = platform_name
    os.environ.setdefault("QT_SCALE_FACTOR_ROUNDING_POLICY", "PassThrough")
    os.environ.setdefault("QT_OPENGL", "software")
    os.environ.setdefault("QT_QUICK_BACKEND", "software")
    os.environ.setdefault("LIBGL_ALWAYS_SOFTWARE", "1")
    os.environ.setdefault("PYTHONUTF8", "1")


def validate_effective_scale(requested: float, effective: float) -> None:
    if effective <= 0:
        raise RuntimeError("Qt returned a non-positive device pixel ratio")
    if effective + 0.05 < requested * 0.9:
        raise RuntimeError(
            f"Qt ignored the requested scale factor: requested={requested:g}, "
            f"effective={effective:g}"
        )


def wait_for_pdf_ready(document: Any, app: Any, *, timeout_seconds: float = 10.0) -> None:
    """Process Qt events until an asynchronously loaded PDF is ready or fails."""

    deadline = time.monotonic() + timeout_seconds
    while True:
        status = document.status()
        status_name = str(getattr(status, "name", status)).casefold()
        if status_name == "ready":
            return
        if status_name == "error":
            raise RuntimeError(f"QPdfDocument failed to load PDF: {document.error()}")
        if time.monotonic() >= deadline:
            raise RuntimeError(
                f"QPdfDocument loading timed out with status: {status_name}"
            )
        app.processEvents()
        time.sleep(0.01)


def build_checklist(
    *,
    scale_factor: float,
    qt_platform: str,
    environment: dict[str, Any],
    cases: Iterable[CaseResult],
    physical: dict[str, Any],
) -> dict[str, Any]:
    case_payload = [asdict(item) for item in cases]
    automated_status = (
        "passed"
        if case_payload and all(item["status"] == "passed" for item in case_payload)
        else "failed"
    )
    physical_status = str(physical.get("status", "not_run"))
    physical_complete = validate_physical_payload(physical) if physical_status == "passed" else False
    if automated_status == "failed" or physical_status == "failed":
        overall_status = "failed"
    elif physical_status == "passed" and not physical_complete:
        overall_status = "failed"
    elif physical_complete:
        overall_status = "passed"
    else:
        overall_status = "pending_physical_printer"
    return {
        "schema": CHECKLIST_SCHEMA,
        "generated_at_utc": datetime.now(UTC).isoformat(),
        "scale_factor": scale_factor,
        "qt_platform": qt_platform,
        "environment": environment,
        "automated": {
            "status": automated_status,
            "cases": case_payload,
        },
        "physical_printer": physical,
        "overall_status": overall_status,
    }


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        validate_physical_arguments(args)
    except ValueError as exc:
        parser.error(str(exc))

    configure_qt_environment(args.scale_factor, args.platform)
    if str(SRC) not in sys.path:
        sys.path.insert(0, str(SRC))

    output_dir = args.output_dir.resolve()
    output_dir.mkdir(parents=True, exist_ok=True)

    app, environment = _create_application(args.scale_factor, args.platform)
    results = tuple(_run_case(app, item, output_dir) for item in AUTOMATED_CASES)
    physical = _run_physical_printer_check(app, args, output_dir)
    checklist = build_checklist(
        scale_factor=args.scale_factor,
        qt_platform=args.platform,
        environment=environment,
        cases=results,
        physical=physical,
    )
    checklist_path = output_dir / "windows-release-checklist.json"
    _write_json(checklist_path, checklist)
    failed_cases = [item for item in results if item.status != "passed"]
    for item in failed_cases:
        print(f"[FAIL] {item.case_id}: {item.error}", file=sys.stderr)
    print(json.dumps(checklist, ensure_ascii=False, indent=2))
    if failed_cases:
        print("Automated acceptance failures:", file=sys.stderr)
        for item in failed_cases:
            print(f"  - {item.case_id}: {item.error}", file=sys.stderr)

    automated_ok = checklist["automated"]["status"] == "passed"
    physical_ok = checklist["overall_status"] == "passed"
    if not automated_ok:
        return 2
    if args.require_physical and not physical_ok:
        return 3
    return 0


def _create_application(scale_factor: float, qt_platform: str):
    from PySide6 import __version__ as pyside_version
    from PySide6.QtCore import QCoreApplication, qVersion
    from PySide6.QtGui import QGuiApplication
    from PySide6.QtWidgets import QApplication

    QCoreApplication.setApplicationName("GEOLOG GASRATIO@Pixler release acceptance")
    app = QApplication.instance() or QApplication([])
    screen = QGuiApplication.primaryScreen()
    environment: dict[str, Any] = {
        "os": platform.platform(),
        "python": platform.python_version(),
        "pyside6": pyside_version,
        "qt": qVersion(),
        "requested_scale_factor": scale_factor,
        "qt_platform": qt_platform,
    }
    if screen is None:
        raise RuntimeError("Qt did not expose a primary screen")
    validate_effective_scale(scale_factor, float(screen.devicePixelRatio()))
    geometry = screen.geometry()
    environment["screen"] = {
        "name": screen.name(),
        "width": geometry.width(),
        "height": geometry.height(),
        "device_pixel_ratio": screen.devicePixelRatio(),
        "logical_dpi": screen.logicalDotsPerInch(),
        "physical_dpi": screen.physicalDotsPerInch(),
    }
    return app, environment


def _run_case(app, case: MatrixCase, output_dir: Path) -> CaseResult:
    from PySide6.QtPdf import QPdfDocument

    from geoworkbench.printing.page_settings import (
        PrintOrientation,
        PrintPageFormat,
        PrintPageSettings,
    )
    from geoworkbench.printing.print_job import (
        PrintExportPreferences,
        PrintJobSettings,
        PrintOutputFormat,
    )
    from geoworkbench.printing.pagination import PrintRangeMode
    from geoworkbench.printing.print_layout import PrintScaleMode
    from geoworkbench.services.localization import AppLanguage
    from geoworkbench.services.print_jobs import PrintJobExecutor
    from geoworkbench.ui.print_center_dialog import PrintCenterDialog

    case_dir = output_dir / case.case_id
    case_dir.mkdir(parents=True, exist_ok=True)
    pdf_path = case_dir / f"{case.case_id}.pdf"
    screenshot_path = case_dir / f"{case.case_id}-print-center.png"
    language = AppLanguage(case.language)
    page = PrintPageSettings(
        page_format=PrintPageFormat(case.page_format),
        orientation=PrintOrientation(case.orientation),
        custom_width_mm=case.custom_width_mm,
        custom_height_mm=case.custom_height_mm,
        scale_mode=PrintScaleMode(case.scale_mode),
        continuation_overlap_mm=5.0,
    )
    dialog = PrintCenterDialog(
        initial_page=page,
        initial_preferences=PrintExportPreferences(
            output_format=PrintOutputFormat.PDF,
            dpi=case.dpi,
            range_mode=PrintRangeMode(case.pagination_mode),
            units_per_page=case.units_per_page,
        ),
        language=language,
        source_name=f"Release acceptance {case.case_id}",
        supports_pagination=True,
        current_vertical_range=(100.0, 150.0),
        full_vertical_range=(100.0, 300.0),
        vertical_unit="m",
    )
    widget = _build_acceptance_widget(case)
    try:
        dialog.path_input.setText(str(pdf_path))
        dialog.show()
        app.processEvents()
        configured_job = dialog.job_settings()
        if configured_job.output_format is not PrintOutputFormat.PDF:
            raise RuntimeError("Print Center did not preserve PDF output")
        if configured_job.page != page or configured_job.dpi != case.dpi:
            raise RuntimeError("Print Center did not preserve the requested page settings")
        if configured_job.pagination.range_mode is not PrintRangeMode(case.pagination_mode):
            raise RuntimeError("Print Center did not preserve the requested page range")
        screenshot = dialog.grab()
        if screenshot.isNull() or not screenshot.save(str(screenshot_path), "PNG"):
            raise RuntimeError("failed to save Print Center screenshot")
        dialog.close()
        app.processEvents()

        widget.show()
        app.processEvents()
        if case.widget_kind == "tablet":
            widget.set_visible_depth(100.0, 150.0)
            app.processEvents()
        job = PrintJobSettings(
            output_format=PrintOutputFormat.PDF,
            target=pdf_path,
            page=page,
            dpi=case.dpi,
            pagination=configured_job.pagination,
        )
        result = PrintJobExecutor().execute_file(
            widget,
            job,
            source_name=f"Windows acceptance: {case.case_id}",
            language=language,
            overwrite=True,
        )
        if result.page_count < case.expected_min_pages:
            raise RuntimeError(
                f"expected at least {case.expected_min_pages} pages, got {result.page_count}"
            )
        if not pdf_path.is_file() or pdf_path.stat().st_size < 1_000:
            raise RuntimeError("PDF evidence was not created or is unexpectedly small")
        if not pdf_path.read_bytes().startswith(b"%PDF"):
            raise RuntimeError("PDF evidence has an invalid signature")

        document = QPdfDocument()
        load_error = document.load(str(pdf_path))
        if load_error != QPdfDocument.Error.None_:
            raise RuntimeError(f"QPdfDocument failed to start loading PDF: {load_error}")
        wait_for_pdf_ready(document, app)
        if document.pageCount() != result.page_count:
            raise RuntimeError(
                "renderer and QPdfDocument page counts differ: "
                f"{result.page_count} != {document.pageCount()}"
            )
        page_sizes = tuple(
            (
                float(document.pagePointSize(index).width()),
                float(document.pagePointSize(index).height()),
            )
            for index in range(document.pageCount())
        )
        if not page_sizes or any(width <= 0 or height <= 0 for width, height in page_sizes):
            raise RuntimeError("PDF contains an invalid page size")
        return CaseResult(
            case_id=case.case_id,
            status="passed",
            page_count=result.page_count,
            pdf_path=_relative_artifact_path(pdf_path, output_dir),
            screenshot_path=_relative_artifact_path(screenshot_path, output_dir),
            pdf_sha256=_sha256(pdf_path),
            pdf_size_bytes=pdf_path.stat().st_size,
            page_sizes_points=page_sizes,
        )
    except Exception as exc:
        return CaseResult(
            case_id=case.case_id,
            status="failed",
            page_count=0,
            pdf_path=_relative_artifact_path(pdf_path, output_dir),
            screenshot_path=_relative_artifact_path(screenshot_path, output_dir),
            pdf_sha256=_sha256(pdf_path) if pdf_path.is_file() else "",
            pdf_size_bytes=pdf_path.stat().st_size if pdf_path.is_file() else 0,
            page_sizes_points=(),
            error=f"{type(exc).__name__}: {exc}",
        )
    finally:
        dialog.close()
        widget.close()
        app.processEvents()


def _build_acceptance_widget(case: MatrixCase):
    if case.widget_kind == "tablet":
        return _build_acceptance_tablet(case)
    if case.widget_kind != "label":
        raise ValueError(f"unsupported acceptance widget kind: {case.widget_kind}")

    from PySide6.QtCore import Qt
    from PySide6.QtGui import QFont, QImage, QPainter
    from PySide6.QtWidgets import QLabel, QVBoxLayout, QWidget

    widget = QWidget()
    widget.setObjectName("physicalAcceptanceSheet")
    widget.resize(case.widget_width, case.widget_height)
    widget.setStyleSheet("QWidget#physicalAcceptanceSheet { background: white; color: black; }")
    layout = QVBoxLayout(widget)
    layout.setContentsMargins(28, 28, 28, 28)

    label = QLabel(
        "GEOLOG GASRATIO@Pixler — Windows release acceptance\n"
        "Custom heading: Описание пород / Тау жыныстарының сипаттамасы\n"
        f"Case: {case.case_id}\n"
        "Interval: 1703.28–1753.28 m — boundaries must remain visible\n"
        "Русский: длинное форматированное описание должно переноситься без обрезания; "
        "тонкие прослои, нефтенасыщенность и трещиноватость сохраняются полностью.\n"
        "Қазақша: ұзын сипаттама жолдарға дұрыс бөлініп, интервал шекарасынан шықпауы тиіс.\n"
        "English: rich-text description must remain readable inside the interval bounds.\n"
        "Colors: RED / GREEN / BLUE / BLACK — distinguish all swatches on paper."
    )
    label.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignTop)
    label.setWordWrap(True)
    label.setFont(QFont("Segoe UI", 14))
    label.setStyleSheet(
        "QLabel { padding: 18px; border: 3px solid #202020; background: white; color: black; }"
    )
    layout.addWidget(label, 3)

    photo = QLabel()
    photo.setAlignment(Qt.AlignmentFlag.AlignCenter)
    photo.setMinimumHeight(max(90, case.widget_height // 5))
    image = QImage(720, 180, QImage.Format.Format_RGB32)
    image.fill(Qt.GlobalColor.white)
    painter = QPainter(image)
    try:
        swatches = (
            (Qt.GlobalColor.red, "RED"),
            (Qt.GlobalColor.green, "GREEN"),
            (Qt.GlobalColor.blue, "BLUE"),
            (Qt.GlobalColor.black, "CUTTINGS PHOTO / ФОТО ШЛАМА"),
        )
        width = image.width() // len(swatches)
        for index, (color, text) in enumerate(swatches):
            x = index * width
            painter.fillRect(x + 8, 8, width - 16, image.height() - 16, color)
            painter.setPen(Qt.GlobalColor.white)
            painter.drawText(
                x + 12,
                12,
                width - 24,
                image.height() - 24,
                Qt.AlignmentFlag.AlignCenter | Qt.TextFlag.TextWordWrap,
                text,
            )
    finally:
        painter.end()
    photo.setPixmap(__import__("PySide6.QtGui", fromlist=["QPixmap"]).QPixmap.fromImage(image))
    photo.setStyleSheet("QLabel { border: 3px solid #202020; background: white; }")
    layout.addWidget(photo, 2)
    return widget


def _build_acceptance_tablet(case: MatrixCase):
    import numpy as np

    from geoworkbench.domain.models import Dataset, DatasetKind, DepthDomain
    from geoworkbench.tablet.models import TabletLayout, TrackDefinition, TrackKind
    from geoworkbench.tablet.tablet_view import TabletView

    dataset = Dataset(
        "release-acceptance-tablet",
        "Ұңғыма Ә-1 / Скважина А-1",
        DatasetKind.GTI,
        DepthDomain.MD,
        np.linspace(100.0, 300.0, 401),
    )
    view = TabletView()
    view.resize(case.widget_width, case.widget_height)
    view.set_layout_model(
        TabletLayout(
            [
                TrackDefinition("depth", "Глубина / Тереңдік", TrackKind.DEPTH, width=120),
                TrackDefinition("gas", "Газ ΔC₁, µg/L", TrackKind.CURVE, width=420),
                TrackDefinition("text", "Описание Ә Ғ Қ", TrackKind.TEXT, width=300),
            ],
            visible_depth_top=100.0,
            visible_depth_bottom=150.0,
        )
    )
    view.set_dataset(dataset)
    return view


def _run_physical_printer_check(app, args: argparse.Namespace, output_dir: Path) -> dict[str, Any]:
    evidence = physical_evidence_from_args(args)
    if not args.printer:
        return {
            "status": "not_run",
            "reason": "No physical printer was supplied to the automated CI environment.",
            "required_for_rel_03": True,
            "required_for_cut_03": True,
            "required_cases": [item.case_id for item in PHYSICAL_CASES],
            "evidence_schema": PHYSICAL_EVIDENCE_SCHEMA,
            "evidence": evidence,
        }

    from PySide6.QtPrintSupport import QPrinter, QPrinterInfo

    from geoworkbench.printing.page_settings import (
        PrintOrientation,
        PrintPageFormat,
        PrintPageSettings,
    )
    from geoworkbench.printing.print_job import PrintJobSettings, PrintOutputFormat
    from geoworkbench.printing.print_layout import PrintScaleMode
    from geoworkbench.services.localization import AppLanguage
    from geoworkbench.services.print_jobs import PrintJobExecutor

    info = QPrinterInfo.printerInfo(args.printer)
    if info.isNull():
        return {
            "status": "failed",
            "printer": args.printer,
            "operator": args.operator,
            "error": "printer-not-found",
            "notes": args.physical_notes,
            "cases": [],
            "evidence_schema": PHYSICAL_EVIDENCE_SCHEMA,
            "evidence": evidence,
        }

    executor = PrintJobExecutor()
    case_results: list[dict[str, Any]] = []
    for case in PHYSICAL_CASES:
        widget = _build_acceptance_widget(case)
        widget.show()
        app.processEvents()
        try:
            printer = QPrinter(info, QPrinter.PrinterMode.HighResolution)
            page = PrintPageSettings(
                page_format=PrintPageFormat(case.page_format),
                orientation=PrintOrientation(case.orientation),
                custom_width_mm=case.custom_width_mm,
                custom_height_mm=case.custom_height_mm,
                scale_mode=PrintScaleMode(case.scale_mode),
                continuation_overlap_mm=5.0,
            )
            job = PrintJobSettings(
                output_format=PrintOutputFormat.PRINTER,
                page=page,
                dpi=case.dpi,
            )
            gate = executor.physical_printer_gate(printer, widget, job)
            item: dict[str, Any] = {
                "case_id": case.case_id,
                "page_format": case.page_format,
                "orientation": case.orientation,
                "scale_mode": case.scale_mode,
                "cut03_required": case.case_id in CUT03_REQUIRED_CASES,
                "gate_ok": gate.ok,
                "selected_dpi": gate.selected_dpi,
                "page_count": gate.page_count,
                "printed": False,
                "issues": [
                    {
                        "code": issue.code,
                        "severity": issue.severity.value,
                        "message": issue.message,
                    }
                    for issue in gate.issues
                ],
            }
            if gate.ok and gate.page_count < case.expected_min_pages:
                item["gate_ok"] = False
                item["issues"].append(
                    {
                        "code": "continuation-page-count",
                        "severity": "error",
                        "message": (
                            f"Expected at least {case.expected_min_pages} pages, "
                            f"got {gate.page_count}."
                        ),
                    }
                )
            if item["gate_ok"] and args.print_test:
                result = executor.render_to_printer(
                    widget,
                    printer,
                    job,
                    source_name=f"Windows physical acceptance: {case.case_id}",
                    language=AppLanguage.EN,
                    require_physical_gate=True,
                )
                item["printed"] = True
                item["page_count"] = result.page_count
            case_results.append(item)
        except Exception as exc:
            case_results.append(
                {
                    "case_id": case.case_id,
                    "page_format": case.page_format,
                    "orientation": case.orientation,
                    "scale_mode": case.scale_mode,
                    "cut03_required": case.case_id in CUT03_REQUIRED_CASES,
                    "gate_ok": False,
                    "printed": False,
                    "error": f"{type(exc).__name__}: {exc}",
                }
            )
        finally:
            widget.close()
            app.processEvents()

    all_gates_ok = bool(case_results) and all(item.get("gate_ok") for item in case_results)
    all_printed = bool(case_results) and all(item.get("printed") for item in case_results)
    evidence_ok = physical_evidence_complete(evidence)
    visually_confirmed = bool(
        args.confirm_physical_output and all_printed and evidence_ok
    )
    if not all_gates_ok:
        status = "failed"
    elif not args.print_test:
        status = "gate_passed_not_printed"
    elif not all_printed:
        status = "failed"
    elif not visually_confirmed:
        status = "printed_pending_visual_confirmation"
    else:
        status = "passed"

    payload = {
        "status": status,
        "printer": info.printerName(),
        "operator": args.operator,
        "notes": args.physical_notes,
        "printed": all_printed,
        "visually_confirmed": visually_confirmed,
        "evidence_schema": PHYSICAL_EVIDENCE_SCHEMA,
        "evidence": evidence,
        "cut03_required_cases": list(CUT03_REQUIRED_CASES),
        "cases": case_results,
    }
    payload["rel03_cut03_evidence_complete"] = validate_physical_payload(payload)
    _write_json(output_dir / "physical-printer-result.json", payload)
    return payload


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    temporary.replace(path)


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _relative_artifact_path(path: Path, output_dir: Path) -> str:
    try:
        return path.relative_to(output_dir).as_posix()
    except ValueError:
        return path.as_posix()


def _format_scale(value: float) -> str:
    return f"{value:g}"


if __name__ == "__main__":
    raise SystemExit(main())
