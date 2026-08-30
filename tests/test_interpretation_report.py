from dataclasses import replace

import fitz
import numpy as np
import pytest
from PySide6.QtGui import QColor, QPalette
from PySide6.QtWidgets import QPushButton, QTextBrowser

from geoworkbench.domain.models import Dataset, DatasetKind, DepthDomain
from geoworkbench.printing.interpretation_report import (
    build_interpretation_report,
    export_interpretation_report_pdf,
    interpretation_report_html,
)
from geoworkbench.project.cuttings_controller import CuttingsController
from geoworkbench.project.session import ProjectSession
from geoworkbench.project.stratigraphy_controller import StratigraphyController
from geoworkbench.services.interval_gas_statistics import (
    build_interval_component_sum_statistics,
)
from geoworkbench.services.localization import AppLanguage
from geoworkbench.ui.interpretation_report_dialog import InterpretationReportDialog


def _session() -> ProjectSession:
    session = ProjectSession()
    session.project.name = "Field <Alpha>"
    depth = np.arange(500.0, 521.0, 1.0)
    dataset = Dataset(
        "dataset",
        "Depth log",
        DatasetKind.GTI,
        DepthDomain.MD,
        depth,
    )
    dataset.upsert_curve("TG", np.arange(100.0, 121.0, 1.0), unit="ppm")
    dataset.upsert_curve("C1", np.arange(1.0, 22.0, 1.0), unit="ppm")
    for mnemonic, value in (
        ("C2", 2.0),
        ("C3", 3.0),
        ("IC4", 4.0),
        ("NC4", 5.0),
        ("IC5", 6.0),
        ("NC5", 7.0),
    ):
        dataset.upsert_curve(mnemonic, np.full(depth.shape, value), unit="ppm")
    session.add_dataset(
        dataset,
        "Well 12",
    )
    controller = CuttingsController(session)
    controller.create_full_sample(
        500.0,
        510.0,
        {"sandstone": 70.0, "clay": 30.0},
        calcite_percent=62.5,
        dolomite_percent=17.5,
        lba_group=3,
        lba_type_id="МСБ",
        lba_intensity=4,
        lba_color="yellow-white",
        lba_distribution="Ring",
        lba_cut="Streaming",
        lba_cut_speed="Slow",
        lba_cut_color="Pale yellow",
        lba_residue_type="Oily residue",
        lba_residue_color="Brown",
        lba_odour="Petroleum",
        lba_stain="Present",
        lba_description="bright <direct> fluorescence",
        analysis_interpretation="Manual conclusion\nRequires correlation",
        description="<p>Fine-grained sandstone &amp; clay.</p>",
    )
    controller.create_full_sample(
        510.0,
        520.0,
        {"limestone": 80.0, "marl": 20.0},
        calcite_percent=40.0,
        description="Limestone with marl interbeds.",
    )
    stratigraphy = StratigraphyController(session)
    stratigraphy.add(
        500.0,
        520.0,
        "K1",
        rank="System / Period",
        name="Lower Cretaceous",
        description="Regional stratigraphic interval",
    )
    stratigraphy.add(
        505.0,
        515.0,
        "K1a",
        rank="Formation",
        name="Albian formation",
        description="Target formation",
    )
    return session


def test_interpretation_report_uses_source_results_and_manual_conclusion() -> None:
    report = build_interpretation_report(_session())

    assert report.project_name == "Field <Alpha>"
    assert report.well_name == "Well 12"
    assert report.dataset_name == "Depth log"
    assert report.calcimetry_count == 2
    assert report.lba_count == 1
    assert report.interpreted_count == 1
    assert report.sample_count == 2
    assert len(report.meter_geology) == 20
    assert len(report.stratigraphy) == 2
    first = report.entries[0]
    assert first.insoluble_residue_percent == 20.0
    assert ("intensity", "4") in first.lba_observations
    assert first.lba_standard_assessment is not None
    assert first.lba_standard_assessment.standard.code == "МСБ"
    assert first.interpretation == "Manual conclusion\nRequires correlation"
    gas = {(item.kind, item.mnemonic): item for item in first.gas_statistics}
    assert gas[("total", "TG")].minimum == 100.0
    assert gas[("total", "TG")].mean == 105.0
    assert gas[("total", "TG")].maximum == 110.0
    assert gas[("component", "C1")].minimum == 1.0
    component_sum = gas[("sum", "SUM_COMPONENTS")]
    assert component_sum.minimum == 28.0
    assert component_sum.mean == 33.0
    assert component_sum.maximum == 38.0
    assert [(item.lithotype_id, item.percentage) for item in first.rock_components] == [
        ("sandstone", 70.0),
        ("clay", 30.0),
    ]
    assert first.rock_description == "Fine-grained sandstone & clay."
    assert {item.code for item in first.stratigraphy} == {"K1", "K1a"}
    first_meter = report.meter_geology[0]
    assert (first_meter.top_depth, first_meter.bottom_depth) == (500.0, 501.0)
    assert first_meter.sampling_coverage == 1.0
    assert first_meter.sample_intervals == ((500.0, 510.0),)
    assert [(item.lithotype_id, item.percentage) for item in first_meter.rock_components] == [
        ("sandstone", 70.0),
        ("clay", 30.0),
    ]


def test_meter_geology_preserves_partial_sampling_and_length_weighted_composition() -> None:
    session = ProjectSession()
    session.add_dataset(
        Dataset(
            "partial",
            "Partial sampling",
            DatasetKind.GTI,
            DepthDomain.MD,
            np.array([100.0, 102.0]),
        ),
        "Well partial",
    )
    controller = CuttingsController(session)
    controller.create_full_sample(
        100.0,
        100.25,
        {"sandstone": 100.0},
        description="Upper quarter",
    )
    controller.create_full_sample(
        100.5,
        101.0,
        {"clay": 100.0},
        description="Lower half",
    )

    report = build_interpretation_report(session)

    assert len(report.meter_geology) == 1
    meter = report.meter_geology[0]
    assert (meter.top_depth, meter.bottom_depth) == (100.0, 101.0)
    assert meter.sampling_coverage == 0.75
    assert meter.sample_intervals == ((100.0, 100.25), (100.5, 101.0))
    components = {item.lithotype_id: item.percentage for item in meter.rock_components}
    assert components["sandstone"] == pytest.approx(100.0 / 3.0)
    assert components["clay"] == pytest.approx(200.0 / 3.0)
    assert meter.rock_descriptions == ("Upper quarter", "Lower half")


def test_component_sum_is_reported_when_total_gas_curve_is_missing() -> None:
    session = ProjectSession()
    dataset = Dataset(
        "gas-without-total",
        "Components only",
        DatasetKind.GTI,
        DepthDomain.MD,
        np.array([100.0, 101.0, 102.0]),
    )
    dataset.upsert_curve("C1", np.array([1.0, 2.0, 3.0]), unit="ppm")
    dataset.upsert_curve("C2", np.array([10.0, 20.0, 30.0]), unit="ppm")
    session.add_dataset(dataset, "Well components")
    CuttingsController(session).create_full_sample(
        100.0,
        102.0,
        {"sandstone": 100.0},
    )

    report = build_interpretation_report(session)
    entry = report.entries[0]

    assert not any(item.kind == "total" for item in entry.gas_statistics)
    component_sum = next(item for item in entry.gas_statistics if item.kind == "sum")
    assert component_sum.minimum == 11.0
    assert component_sum.mean == 22.0
    assert component_sum.maximum == 33.0
    assert component_sum.unit == "ppm"
    html = interpretation_report_html(report, AppLanguage.RU)
    assert "Сумма компонентов [ppm]" in html
    assert "Total Gas (отдельная кривая)" not in html


def test_component_sum_converts_compatible_mixed_units_and_rejects_incompatible_units() -> None:
    dataset = Dataset(
        "mixed-gas-units",
        "Mixed gas units",
        DatasetKind.GTI,
        DepthDomain.MD,
        np.array([100.0, 101.0]),
    )
    dataset.upsert_curve("C1", np.array([10_000.0, 20_000.0]), unit="ppm")
    c2 = dataset.upsert_curve("C2", np.array([2.0, 3.0]), unit="%vol")

    statistics = build_interval_component_sum_statistics(dataset, 100.0, 101.0)

    assert statistics is not None
    assert statistics.unit == "%vol"
    assert statistics.minimum == 3.0
    assert statistics.mean == 4.0
    assert statistics.maximum == 5.0

    c2.metadata = replace(c2.metadata, unit="kg/m3")
    assert build_interval_component_sum_statistics(dataset, 100.0, 101.0) is None


def test_interpretation_report_html_is_localized_and_escapes_project_data() -> None:
    report = build_interpretation_report(_session())

    html = interpretation_report_html(report, AppLanguage.RU)
    english = interpretation_report_html(report, AppLanguage.EN)

    assert "Геологический отчёт по шламу, стратиграфии, газу, кальциметрии и ЛБА" in html
    assert "Описание пород по метровым интервалам" in html
    assert "Фактические интервалы отбора шлама" in html
    assert "Стратиграфия по всей глубине скважины" in html
    assert "Газ и ЛБА по фактическим интервалам отбора" in html
    assert "Total Gas (отдельная кривая): TG [ppm]" in html
    assert "Сумма компонентов [ppm]" in html
    assert "мин 28; среднее 33; макс 38" in html
    assert "не подменяет Total Gas" in html
    assert "Песчаник (SANDSTONE): 70%" in html
    assert "500-510 m" in html
    assert "Lower Cretaceous" in html
    assert "Fine-grained sandstone &amp; clay." in html
    assert "Нерастворимый остаток: 20%" in html
    assert "Интенсивность:</b> 4" in html
    assert "Field &lt;Alpha&gt;" in html
    assert "bright &lt;direct&gt; fluorescence" in html
    assert "Скорость cut:</b> Slow" in html
    assert "Цвет остатка:</b> Brown" in html
    assert "Запах:</b> Petroleum" in html
    assert "Масляное окрашивание:</b> Present" in html
    assert "Оценка по стандарту ЛБА" in html
    assert "МСБ — маслянисто-смолистый битумоид" in html
    assert "html, body { background: #ffffff; color: #172033; }" in html
    assert "td { background: #ffffff; color: #172033; }" in html
    assert "Geological report: cuttings, stratigraphy, gas, calcimetry and LBA" in english
    assert "Rock description by one-metre interval" in english
    assert "This report is not an automatic" in english


def test_interpretation_report_exports_pdf(qapp, tmp_path) -> None:
    report = build_interpretation_report(_session())
    target = tmp_path / "interpretation.pdf"

    exported = export_interpretation_report_pdf(report, target, language=AppLanguage.EN)

    assert exported == target
    assert target.read_bytes().startswith(b"%PDF")
    assert target.stat().st_size > 1000
    with fitz.open(target) as document:
        text = "\n".join(page.get_text() for page in document)
        assert document.page_count >= 3
    assert "Rock description by one-metre interval" in text
    assert "Actual cuttings sampling intervals" in text
    assert "Whole-well stratigraphy" in text
    assert "Gas and LBA by actual sampling interval" in text
    assert "Component sum [ppm]" in text
    assert "Petroleum" in text
    assert "Lower Cretaceous" in text


def test_interpretation_report_dialog_previews_report(qapp) -> None:
    dialog = InterpretationReportDialog(_session(), language=AppLanguage.EN)
    dark_palette = QPalette(dialog.palette())
    dark_palette.setColor(QPalette.ColorRole.Window, QColor("#252a31"))
    dark_palette.setColor(QPalette.ColorRole.Base, QColor("#30363d"))
    dark_palette.setColor(QPalette.ColorRole.Text, QColor("#e5e7eb"))
    dialog.setPalette(dark_palette)
    dialog.show()
    qapp.processEvents()

    preview = dialog.findChild(QTextBrowser, "interpretation-report-preview")
    export_button = dialog.findChild(QPushButton, "interpretation-report-export")

    assert preview is not None
    assert "Manual conclusion" in preview.toPlainText()
    assert "background-color: #ffffff" in preview.styleSheet()
    assert "color: #172033" in preview.styleSheet()
    viewport = preview.viewport()
    image = viewport.grab().toImage()
    canvas_pixel = image.pixelColor(max(0, image.width() - 8), max(0, image.height() - 8))
    assert canvas_pixel.lightness() > 220
    assert export_button is not None and export_button.text() == "Export PDF..."
    dialog.close()
