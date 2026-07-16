import numpy as np
from PySide6.QtPrintSupport import QPrinter

from geoworkbench.domain.models import (
    Dataset,
    DatasetKind,
    DepthDomain,
    MasterlogColumnTemplate,
    MasterlogHeaderElement,
    MasterlogTemplate,
)
from geoworkbench.project.session import ProjectSession
from geoworkbench.printing.masterlog_renderer import (
    curve_x_range,
    configure_masterlog_printer,
    export_masterlog_pdf,
    masterlog_depth_range,
    masterlog_page_ranges,
    masterlog_size_mm,
    render_masterlog_to_printer,
)


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
            MasterlogHeaderElement(
                "line", "line", 5.0, 20.0, 100.0, 0.5, {"color": "#000000"}
            ),
        ],
        columns=[
            MasterlogColumnTemplate("depth", "Depth", "depth", 25.0),
            MasterlogColumnTemplate(
                "gas", "Gas", "curves", 45.0, ["TG", "C1"], show_legend=True
            ),
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
    column.x_scale = "logarithmic"
    assert curve_x_range(column, dataset) == (1.0, 1000.0)


def test_masterlog_pdf_renders_active_dataset_curves(qapp, tmp_path) -> None:
    target = tmp_path / "curves.pdf"

    export_masterlog_pdf(make_template(), make_session_with_curves(), target)

    assert target.read_bytes().startswith(b"%PDF")
    assert target.stat().st_size > 1000


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
