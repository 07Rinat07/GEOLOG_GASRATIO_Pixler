from geoworkbench.domain.models import MasterlogColumnTemplate, MasterlogHeaderElement, MasterlogTemplate
from geoworkbench.project.session import ProjectSession
from geoworkbench.printing.masterlog_renderer import export_masterlog_pdf, masterlog_size_mm


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
