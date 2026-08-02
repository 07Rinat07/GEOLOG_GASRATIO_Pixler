#!/usr/bin/env python3
"""Generate visual evidence for the complete A4 landscape print contract."""

from __future__ import annotations

from copy import deepcopy
import json
from pathlib import Path
import sys
import time

import numpy as np


CURVE_SPECS = {
    "ROP": ("Скорость проходки", "m/h", 4.0, 76.0, 0.2),
    "HKLD": ("Нагрузка на крюке", "t", 0.0, 64.0, 0.9),
    "RPM": ("Обороты ротора", "rpm", 0.0, 122.0, 1.7),
    "FLOW": ("Расход на входе", "L/s", 18.0, 30.0, 0.4),
    "SPP": ("Давление на манифольде", "atm", 20.0, 126.0, 1.3),
    "TG": ("Суммарный газ", "%", 0.0, 0.1437, 0.5),
    "NG": ("Нормализованный газ", "%", 0.0, 0.1437, 1.1),
    "C1": ("Метан C1", "%", 0.0, 0.0919, 0.1),
    "C2": ("Этан C2", "%", 0.0, 0.0082, 0.6),
    "C3": ("Пропан C3", "%", 0.0, 0.0066, 1.2),
    "IC4": ("Изобутан iC4", "%", 0.0, 0.0024, 1.8),
    "NC4": ("Нормальный бутан nC4", "%", 0.0, 0.0088, 2.4),
    "IC5": ("Изопентан iC5", "%", 0.0, 0.0044, 3.0),
}
PALETTE = ("#2563eb", "#dc2626", "#16a34a", "#9333ea", "#ea580c", "#0891b2")


def _wave(depth: np.ndarray, minimum: float, maximum: float, phase: float) -> np.ndarray:
    midpoint = (minimum + maximum) / 2.0
    amplitude = (maximum - minimum) / 2.35
    values = midpoint + amplitude * (
        0.58 * np.sin(depth / 23.0 + phase)
        + 0.29 * np.sin(depth / 7.0 + phase * 0.7)
        + 0.13 * np.cos(depth / 3.0 + phase * 1.4)
    )
    return np.clip(values, minimum, maximum)


def _curve_track(
    track_id: str,
    title: str,
    mnemonics: tuple[str, ...],
    width: int,
    group_title: str,
):
    from geoworkbench.tablet.models import (
        CurveDisplaySettings,
        CurveStyle,
        TrackDefinition,
        TrackKind,
        XScale,
    )

    return TrackDefinition(
        track_id,
        title,
        TrackKind.CURVE,
        list(mnemonics),
        width=width,
        group_title=group_title,
        grid_major_divisions=5,
        grid_minor_divisions=5,
        grid_alpha=0.26,
        curve_styles={
            mnemonic: CurveStyle(PALETTE[index % len(PALETTE)], 1.5)
            for index, mnemonic in enumerate(mnemonics)
        },
        curve_display={
            mnemonic: CurveDisplaySettings(
                display_name=CURVE_SPECS[mnemonic][0],
                x_scale=XScale.LINEAR,
                x_min=CURVE_SPECS[mnemonic][2],
                x_max=CURVE_SPECS[mnemonic][3],
                unit_override=CURVE_SPECS[mnemonic][1],
                header_line_color=PALETTE[index % len(PALETTE)],
            )
            for index, mnemonic in enumerate(mnemonics)
        },
    )


def build_control_tablet():
    from geoworkbench.domain.models import Dataset, DatasetKind, DepthDomain
    from geoworkbench.tablet.models import TabletLayout, TrackDefinition, TrackKind
    from geoworkbench.tablet.tablet_view import TabletView

    depth = np.linspace(0.0, 2000.0, 4001)
    dataset = Dataset(
        "a4-control-dataset",
        "Контрольный набор ГТИ",
        DatasetKind.GTI,
        DepthDomain.MD,
        depth,
    )
    dataset.headers.update(
        {
            "WELL": "К-101",
            "FIELD": "Контрольное месторождение",
            "CLIENT": "АО Заказчик",
            "CONTRACTOR": "ТОО Исполнитель",
            "RIG": "БУ-5000",
        }
    )
    for mnemonic, (name, unit, minimum, maximum, phase) in CURVE_SPECS.items():
        dataset.upsert_curve(
            mnemonic,
            _wave(depth, minimum, maximum, phase),
            unit=unit,
            description=name,
            provenance="acceptance:a4-masterlog-control",
        )

    tracks = [
        TrackDefinition(
            "depth", "Глубина, м", TrackKind.DEPTH, width=110, group_title="Геология"
        ),
        _curve_track(
            "drilling",
            "Бурение",
            ("ROP", "HKLD", "RPM"),
            430,
            "Технология бурения",
        ),
        _curve_track(
            "mud",
            "Буровой раствор",
            ("FLOW", "SPP"),
            410,
            "Технологические параметры",
        ),
        _curve_track(
            "raw-gas",
            "Сырой и нормализованный газ",
            ("TG", "NG"),
            440,
            "Газовый каротаж",
        ),
        _curve_track(
            "components",
            "Газ C1–C5",
            ("C1", "C2", "C3", "IC4", "NC4", "IC5"),
            520,
            "Компонентный состав газа",
        ),
    ]
    view = TabletView()
    view.resize(1910, 900)
    view.set_layout_model(
        TabletLayout(tracks, visible_depth_top=0.0, visible_depth_bottom=50.0)
    )
    view.set_dataset(dataset)
    return view, dataset


def build_header_template():
    from geoworkbench.printing.masterlog_presets import BUILTIN_MASTERLOG_FORM_PRESETS

    preset = next(
        item
        for item in BUILTIN_MASTERLOG_FORM_PRESETS
        if item.preset_id == "kazgeology_reference_blank"
    )
    template = deepcopy(preset.template)
    template.page_format = "A4"
    template.properties["orientation"] = "landscape"
    template.properties["header_fields"] = {
        "header.country": "Республика Казахстан",
        "header.region": "Атырауская область",
        "header.district": "Контрольный участок",
        "header.field": "Контрольное месторождение",
        "header.well_number": "К-101",
        "header.customer": "АО Заказчик",
        "header.contractor": "ТОО Исполнитель",
        "header.drilling_company": "ТОО Буровая компания",
        "header.actual_depth": "2000 м",
        "header.project_depth": "2200 м",
        "header.interval": "0–2000 м",
        "header.scale": "Авто, A4 альбомная",
        "header.rig": "БУ-5000",
        "header.engineers": "Инженер ГТИ / Геолог",
    }
    return template


def _wait_for_pdf(document, app) -> None:
    deadline = time.monotonic() + 10.0
    while True:
        status = document.status()
        status_name = str(getattr(status, "name", status)).casefold()
        if status_name == "ready":
            return
        if status_name == "error" or time.monotonic() >= deadline:
            raise RuntimeError(f"PDF status: {status}")
        app.processEvents()
        time.sleep(0.01)


def render_control(output_dir: Path) -> dict[str, object]:
    from PySide6.QtCore import QSize
    from PySide6.QtPdf import QPdfDocument
    from PySide6.QtWidgets import QApplication

    from geoworkbench.printing.document_renderer import PrintDocumentContext, build_document_plan
    from geoworkbench.printing.page_settings import (
        PrintOrientation,
        PrintPageFormat,
        PrintPageSettings,
    )
    from geoworkbench.printing.pagination import PrintPaginationSettings, PrintRangeMode
    from geoworkbench.printing.print_job import (
        PrintHeaderPlacement,
        PrintJobSettings,
        PrintOutputFormat,
    )
    from geoworkbench.printing.print_layout import PrintScaleMode
    from geoworkbench.project.session import ProjectSession
    from geoworkbench.services.localization import AppLanguage
    from geoworkbench.services.print_jobs import PrintJobExecutor

    app = QApplication.instance() or QApplication([])
    output_dir.mkdir(parents=True, exist_ok=True)
    pdf_path = output_dir / "a4-landscape-auto-masterlog-control.pdf"
    view, dataset = build_control_tablet()
    template = build_header_template()
    session = ProjectSession()
    session.project.name = "Контроль единого адаптива A4"
    session.add_dataset(dataset, "Скважина К-101")

    page = PrintPageSettings(
        page_format=PrintPageFormat.A4,
        orientation=PrintOrientation.LANDSCAPE,
        fit_form_columns=True,
        scale_mode=PrintScaleMode.FIT,
    )
    job = PrintJobSettings(
        output_format=PrintOutputFormat.PDF,
        target=pdf_path,
        page=page,
        dpi=300,
        pagination=PrintPaginationSettings(
            range_mode=PrintRangeMode.FULL,
            units_per_page=50.0,
            auto_units_per_page=True,
            overlap=0.0,
        ),
        header_template_id=template.template_id,
        header_placement=PrintHeaderPlacement.FIRST_PAGE,
        repeat_column_header_at_bottom=True,
    )
    context = PrintDocumentContext(
        "Контрольный Masterlog A4",
        AppLanguage.RU,
        header_template=template,
        session=session,
    )

    view.show()
    app.processEvents()
    view.set_visible_depth(0.0, 50.0)
    app.processEvents()
    try:
        plan = build_document_plan(view, job, context=context)
        if plan.page_count < 3:
            raise RuntimeError(f"Expected at least 3 pages, got {plan.page_count}")
        if (
            plan.first_page_units_per_page is None
            or plan.resolved_units_per_page is None
            or plan.first_page_units_per_page >= plan.resolved_units_per_page
        ):
            raise RuntimeError("First page did not reduce its automatic depth interval")
        result = PrintJobExecutor().execute_file(
            view,
            job,
            source_name=context.title,
            language=context.language,
            overwrite=True,
            header_template=template,
            session=session,
        )
    finally:
        view.close()
        app.processEvents()

    document = QPdfDocument()
    error = document.load(str(pdf_path))
    if error != QPdfDocument.Error.None_:
        raise RuntimeError(f"QPdfDocument load failed: {error}")
    _wait_for_pdf(document, app)
    if document.pageCount() != result.page_count:
        raise RuntimeError("Renderer and PDF page counts differ")

    preview_names = ("first-page.png", "second-page.png", "last-page.png")
    page_indexes = (0, 1, document.pageCount() - 1)
    for page_index, name in zip(page_indexes, preview_names, strict=True):
        point_size = document.pagePointSize(page_index)
        width = 2200
        height = max(1, round(width * point_size.height() / point_size.width()))
        image = document.render(page_index, QSize(width, height))
        if image.isNull() or not image.save(str(output_dir / name), "PNG"):
            raise RuntimeError(f"Failed to render preview: {name}")

    page_sizes = [
        [
            float(document.pagePointSize(index).width()),
            float(document.pagePointSize(index).height()),
        ]
        for index in range(document.pageCount())
    ]
    if any(width <= height for width, height in page_sizes):
        raise RuntimeError("Control PDF is not landscape on every page")

    payload: dict[str, object] = {
        "pdf": pdf_path.name,
        "previews": list(preview_names),
        "page_count": result.page_count,
        "page_sizes_points": page_sizes,
        "settings": {
            "page_format": "A4",
            "orientation": "landscape",
            "scale_mode": "fit",
            "fit_form_columns": True,
            "auto_units_per_page": True,
            "header_placement": "first_page",
            "repeat_column_header_at_bottom": True,
        },
        "first_page_units_per_page": plan.first_page_units_per_page,
        "regular_units_per_page": plan.resolved_units_per_page,
        "target_content_height_px": plan.target_content_height_px,
        "first_page_target_content_height_px": plan.first_page_target_content_height_px,
    }
    (output_dir / "control-metadata.json").write_text(
        json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    return payload


def main(argv: list[str] | None = None) -> int:
    args = list(sys.argv[1:] if argv is None else argv)
    output_dir = Path(args[0]) if args else Path("build/ci-artifacts/a4-masterlog-control")
    print(json.dumps(render_control(output_dir.resolve()), ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
