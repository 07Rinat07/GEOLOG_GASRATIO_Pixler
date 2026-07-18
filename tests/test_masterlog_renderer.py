import numpy as np
import pytest
from PySide6.QtCore import QRectF
from PySide6.QtGui import QImage, QPainter
from PySide6.QtPrintSupport import QPrinter

from geoworkbench.domain.models import (
    Dataset,
    DatasetKind,
    DepthDomain,
    CuttingsSample,
    MasterlogColumnTemplate,
    MasterlogHeaderElement,
    MasterlogTemplate,
    LithologyInterval,
    ProjectLithotype,
)
from geoworkbench.project.session import ProjectSession
from geoworkbench.printing.image_assets import create_svg_asset
from geoworkbench.printing.masterlog_renderer import (
    MasterlogRenderError,
    curve_x_range,
    configure_masterlog_printer,
    export_masterlog_pdf,
    masterlog_depth_range,
    masterlog_column_groups,
    masterlog_page_ranges,
    masterlog_size_mm,
    paint_masterlog,
    render_masterlog_to_printer,
    _parameter_symbol_x,
    visible_lithology_intervals,
    masterlog_curve_bindings,
)
from geoworkbench.printing.masterlog_output import MasterlogOutputSettings
from geoworkbench.services.localization import AppLanguage


def make_template() -> MasterlogTemplate:
    return MasterlogTemplate(
        "standard",
        "Standard",
        page_format="roll",
        header_height_mm=40.0,
        header_elements=[
            MasterlogHeaderElement(
                "title", "field", 5.0, 5.0, 80.0, 10.0, {"field": "project.name"}
            ),
            MasterlogHeaderElement("line", "line", 5.0, 20.0, 100.0, 0.5, {"color": "#000000"}),
        ],
        columns=[
            MasterlogColumnTemplate("depth", "Depth", "depth", 25.0),
            MasterlogColumnTemplate("gas", "Gas", "curves", 45.0, ["TG", "C1"], show_legend=True),
        ],
        properties={"body_height_mm": 300.0},
    )


def test_masterlog_size_uses_mm_template_geometry() -> None:
    size = masterlog_size_mm(make_template())

    assert size.width() == 70.0
    assert size.height() == 340.0


def test_masterlog_pdf_export_is_independent_and_atomic(qapp, tmp_path) -> None:
    target = tmp_path / "masterlog.pdf"

    result = export_masterlog_pdf(make_template(), ProjectSession(), target)

    assert result == target
    assert target.read_bytes().startswith(b"%PDF")
    assert target.stat().st_size > 500


def make_session_with_curves() -> ProjectSession:
    dataset = Dataset(
        "dataset-1",
        "Well log",
        DatasetKind.GTI,
        DepthDomain.MD,
        np.array([100.0, 125.0, 150.0, 175.0, 200.0]),
    )
    dataset.upsert_curve("TG", np.array([1.0, 10.0, 100.0, np.nan, 1000.0]))
    dataset.upsert_curve("C1", np.array([2.0, 4.0, 8.0, 16.0, 32.0]))
    session = ProjectSession()
    session.add_dataset(dataset, "Well")
    return session


def test_masterlog_depth_scale_controls_roll_height() -> None:
    session = make_session_with_curves()
    template = make_template()
    template.depth_scale = 500

    assert masterlog_depth_range(session) == (100.0, 200.0)
    assert masterlog_size_mm(template, session).height() == 252.0


def test_masterlog_curve_range_supports_auto_linear_and_logarithmic() -> None:
    dataset = make_session_with_curves().current_dataset
    assert dataset is not None
    column = make_template().columns[1]

    assert curve_x_range(column, dataset) == (1.0, 1000.0)


def test_masterlog_curve_range_uses_saved_vendor_curve_mapping() -> None:
    session = make_session_with_curves()
    dataset = session.current_dataset
    assert dataset is not None
    vendor = dataset.upsert_curve("VENDOR_TOTAL", np.array([20.0, 40.0, 60.0, 80.0, 100.0]))
    template = MasterlogTemplate(
        "mapped",
        "Mapped",
        columns=[MasterlogColumnTemplate("gas", "Gas", "curves", 40.0, ["CUSTOM_TG"])],
        properties={
            "dataset_curve_bindings": {dataset.dataset_id: {"CUSTOM_TG": vendor.metadata.curve_id}}
        },
    )
    bindings = masterlog_curve_bindings(template, dataset)

    assert curve_x_range(template.columns[0], dataset, bindings) == (20.0, 100.0)


def test_parameter_symbol_x_follows_linear_and_log_column_scale() -> None:
    dataset = make_session_with_curves().current_dataset
    assert dataset is not None
    column = make_template().columns[1]
    rect = QRectF(0.0, 0.0, 100.0, 200.0)

    linear = _parameter_symbol_x(rect, column, dataset, "TG", 150.0)
    column.x_scale = "logarithmic"
    logarithmic = _parameter_symbol_x(rect, column, dataset, "TG", 150.0)

    assert linear == pytest.approx(9.91, abs=0.1)
    assert logarithmic == pytest.approx(66.67, abs=0.1)
    assert _parameter_symbol_x(rect, column, dataset, "ROP", 150.0) is None
    column.x_scale = "logarithmic"
    assert curve_x_range(column, dataset) == (1.0, 1000.0)


def test_masterlog_pdf_renders_active_dataset_curves(qapp, tmp_path) -> None:
    target = tmp_path / "curves.pdf"

    export_masterlog_pdf(make_template(), make_session_with_curves(), target)

    assert target.read_bytes().startswith(b"%PDF")
    assert target.stat().st_size > 1000


def test_masterlog_renders_lithology_and_description_columns(qapp) -> None:
    session = make_session_with_curves()
    assert session.current_well is not None
    session.project.lithotypes["sand"] = ProjectLithotype(
        "sand", "SS", "Песчаник", "Sandstone", "sedimentary", "#facc15", "solid"
    )
    session.current_well.lithology = [
        LithologyInterval("layer", 110.0, 160.0, "sand", "Песчаник мелкозернистый")
    ]
    template = MasterlogTemplate(
        "geology",
        "Geology",
        depth_scale=500,
        header_height_mm=40.0,
        columns=[
            MasterlogColumnTemplate("lith", "Lithology", "lithology", 30.0),
            MasterlogColumnTemplate("description", "Description", "text", 50.0),
        ],
    )
    image = QImage(800, 2520, QImage.Format.Format_ARGB32_Premultiplied)
    image.fill(0xFFFFFFFF)
    painter = QPainter(image)
    paint_masterlog(painter, QRectF(0.0, 0.0, 800.0, 2520.0), template, session)
    painter.end()

    color = image.pixelColor(100, 1000)
    assert color.red() > 200 and color.green() > 150 and color.blue() < 80
    assert visible_lithology_intervals(session.current_well.lithology, (100.0, 150.0)) == (
        session.current_well.lithology[0],
    )


def test_masterlog_renders_calcimetry_and_lba_columns(qapp) -> None:
    session = make_session_with_curves()
    assert session.current_well is not None
    session.current_well.cuttings.append(
        CuttingsSample(
            "sample",
            110.0,
            160.0,
            calcite_percent=65.0,
            dolomite_percent=20.0,
            lba_type_id="Oil show",
            lba_intensity=3,
            lba_color="yellow",
            lba_cut="Streaming",
        )
    )
    template = MasterlogTemplate(
        "analysis",
        "Sample analysis",
        depth_scale=500,
        header_height_mm=40.0,
        columns=[
            MasterlogColumnTemplate("calc", "Calcimetry", "calcimetry", 50.0),
            MasterlogColumnTemplate("lba", "LBA", "lba", 50.0),
        ],
    )
    image = QImage(800, 2520, QImage.Format.Format_ARGB32_Premultiplied)
    image.fill(0xFFFFFFFF)
    painter = QPainter(image)

    paint_masterlog(painter, QRectF(0.0, 0.0, 800.0, 2520.0), template, session)
    painter.end()

    assert image.pixelColor(100, 1000) != image.pixelColor(700, 100)


def test_visible_lithology_intervals_excludes_non_intersecting_layers() -> None:
    intervals = (
        LithologyInterval("above", 0.0, 50.0, "sand"),
        LithologyInterval("inside", 100.0, 120.0, "sand"),
        LithologyInterval("below", 200.0, 250.0, "sand"),
    )

    assert visible_lithology_intervals(intervals, (90.0, 150.0)) == (intervals[1],)


def test_masterlog_renders_depth_symbol_in_bound_column(qapp, tmp_path) -> None:
    session = make_session_with_curves()
    template = MasterlogTemplate(
        "symbols",
        "Symbols",
        depth_scale=500,
        header_height_mm=40.0,
        columns=[MasterlogColumnTemplate("gas", "Gas", "curves", 40.0)],
    )
    session.project.masterlog_templates[template.template_id] = template
    source = tmp_path / "red.svg"
    source.write_text(
        '<svg xmlns="http://www.w3.org/2000/svg" width="10" height="10"><rect width="10" height="10" fill="#ff0000"/></svg>',
        encoding="utf-8",
    )
    asset = create_svg_asset(source)
    session.image_assets[asset.asset_id] = asset
    from geoworkbench.project.masterlog_symbol_controller import MasterlogSymbolController

    MasterlogSymbolController(session).add(
        template.template_id,
        depth=150.0,
        column_id="gas",
        asset_ref=asset.asset_id,
        width_mm=8.0,
        height_mm=8.0,
    )
    image = QImage(400, 2520, QImage.Format.Format_ARGB32_Premultiplied)
    image.fill(0xFFFFFFFF)
    painter = QPainter(image)
    paint_masterlog(painter, QRectF(0.0, 0.0, 400.0, 2520.0), template, session)
    painter.end()

    color = image.pixelColor(200, 1520)
    assert color.red() > 200 and color.green() < 80 and color.blue() < 80


def test_masterlog_stretches_interval_symbol_across_depth_range(qapp, tmp_path) -> None:
    session = make_session_with_curves()
    template = MasterlogTemplate(
        "intervals",
        "Intervals",
        depth_scale=500,
        header_height_mm=40.0,
        columns=[MasterlogColumnTemplate("gas", "Gas", "curves", 40.0)],
    )
    session.project.masterlog_templates[template.template_id] = template
    source = tmp_path / "zone.svg"
    source.write_text(
        '<svg xmlns="http://www.w3.org/2000/svg" width="10" height="10"><rect width="10" height="10" fill="#ff0000"/></svg>',
        encoding="utf-8",
    )
    asset = create_svg_asset(source)
    session.image_assets[asset.asset_id] = asset
    from geoworkbench.project.masterlog_symbol_controller import MasterlogSymbolController

    MasterlogSymbolController(session).add(
        template.template_id,
        depth=120.0,
        bottom_depth=180.0,
        anchor_type="interval",
        column_id="gas",
        asset_ref=asset.asset_id,
        width_mm=8.0,
        height_mm=8.0,
    )
    image = QImage(400, 2520, QImage.Format.Format_ARGB32_Premultiplied)
    image.fill(0xFFFFFFFF)
    painter = QPainter(image)
    paint_masterlog(painter, QRectF(0.0, 0.0, 400.0, 2520.0), template, session)
    painter.end()

    for y in (1000, 2000):
        color = image.pixelColor(200, y)
        assert color.red() > 200 and color.green() < 80 and color.blue() < 80


def test_masterlog_a4_page_ranges_follow_depth_scale() -> None:
    dataset = Dataset(
        "dataset-long",
        "Long log",
        DatasetKind.GTI,
        DepthDomain.MD,
        np.array([100.0, 200.0, 300.0, 400.0]),
    )
    session = ProjectSession()
    session.add_dataset(dataset, "Well")
    template = make_template()
    template.page_format = "A4"
    template.depth_scale = 500

    ranges = masterlog_page_ranges(template, session)

    assert ranges == ((100.0, 222.5), (222.5, 345.0), (345.0, 400.0))


def test_masterlog_a4_pdf_contains_multiple_pages(qapp, tmp_path) -> None:
    dataset = Dataset(
        "dataset-long",
        "Long log",
        DatasetKind.GTI,
        DepthDomain.MD,
        np.linspace(100.0, 400.0, 301),
    )
    dataset.upsert_curve("TG", np.linspace(1.0, 100.0, 301))
    session = ProjectSession()
    session.add_dataset(dataset, "Well")
    template = make_template()
    template.page_format = "A4"
    target = tmp_path / "multipage.pdf"

    export_masterlog_pdf(template, session, target)

    payload = target.read_bytes()
    assert payload.startswith(b"%PDF")
    assert b"/Count 3" in payload


def test_masterlog_qprinter_uses_same_multipage_renderer(qapp, tmp_path) -> None:
    dataset = Dataset(
        "dataset-printer",
        "Printer log",
        DatasetKind.GTI,
        DepthDomain.MD,
        np.linspace(100.0, 400.0, 301),
    )
    dataset.upsert_curve("TG", np.linspace(1.0, 100.0, 301))
    session = ProjectSession()
    session.add_dataset(dataset, "Well")
    template = make_template()
    template.page_format = "A4"
    target = tmp_path / "printer.pdf"
    printer = QPrinter(QPrinter.PrinterMode.HighResolution)
    printer.setOutputFormat(QPrinter.OutputFormat.PdfFormat)
    printer.setOutputFileName(str(target))
    configure_masterlog_printer(printer, template, session)

    render_masterlog_to_printer(printer, template, session)

    payload = target.read_bytes()
    assert payload.startswith(b"%PDF")
    assert b"/Count 3" in payload


def test_masterlog_output_interval_changes_page_ranges_and_language(qapp, tmp_path) -> None:
    dataset = Dataset(
        "dataset-output",
        "Output log",
        DatasetKind.GTI,
        DepthDomain.MD,
        np.linspace(100.0, 400.0, 301),
    )
    session = ProjectSession()
    session.add_dataset(dataset, "Well")
    template = make_template()
    template.page_format = "A4"
    settings = MasterlogOutputSettings(150.0, 300.0, AppLanguage.EN)

    assert masterlog_page_ranges(template, session, settings) == (
        (150.0, 272.5),
        (272.5, 300.0),
    )
    target = tmp_path / "interval.pdf"
    export_masterlog_pdf(template, session, target, settings=settings)
    assert b"/Count 2" in target.read_bytes()

    with pytest.raises(MasterlogRenderError):
        masterlog_page_ranges(
            template,
            session,
            MasterlogOutputSettings(50.0, 300.0),
        )


def test_masterlog_custom_page_size_controls_pagination(qapp, tmp_path) -> None:
    session = make_session_with_curves()
    template = make_template()
    template.page_format = "custom"
    template.properties["custom_width_mm"] = 250.0
    template.properties["custom_height_mm"] = 200.0
    template.depth_scale = 500

    assert masterlog_page_ranges(template, session) == (
        (100.0, 174.0),
        (174.0, 200.0),
    )
    target = tmp_path / "custom.pdf"
    export_masterlog_pdf(template, session, target)
    assert b"/Count 2" in target.read_bytes()


def test_masterlog_orientation_controls_horizontal_column_groups() -> None:
    template = make_template()
    template.page_format = "A4"
    template.columns = [
        MasterlogColumnTemplate(f"column-{index}", f"Column {index}", "curves", 80.0)
        for index in range(3)
    ]

    portrait = masterlog_column_groups(template, 210.0)
    template.properties["orientation"] = "landscape"
    landscape = masterlog_column_groups(template, 297.0)

    assert [len(group) for group in portrait] == [2, 1]
    assert [len(group) for group in landscape] == [3]


def test_masterlog_pdf_combines_column_and_depth_pages(qapp, tmp_path) -> None:
    dataset = Dataset(
        "dataset-wide",
        "Wide log",
        DatasetKind.GTI,
        DepthDomain.MD,
        np.linspace(100.0, 300.0, 201),
    )
    session = ProjectSession()
    session.add_dataset(dataset, "Well")
    template = make_template()
    template.page_format = "A4"
    template.columns = [
        MasterlogColumnTemplate(f"column-{index}", f"Column {index}", "curves", 80.0)
        for index in range(3)
    ]
    target = tmp_path / "wide.pdf"

    export_masterlog_pdf(template, session, target)

    assert b"/Count 4" in target.read_bytes()
