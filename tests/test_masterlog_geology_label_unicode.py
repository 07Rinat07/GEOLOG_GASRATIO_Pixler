from copy import deepcopy

import fitz
import numpy as np
import pytest
from PySide6.QtCore import QRectF
from PySide6.QtGui import QFont, QPainter, QPdfWriter

from geoworkbench.domain.models import CuttingsSample, MasterlogColumnTemplate, StratigraphyInterval
from geoworkbench.printing import masterlog_renderer as renderer
from geoworkbench.printing.masterlog_output import MasterlogOutputSettings
from geoworkbench.printing.unicode_support import resolve_unicode_font_profile
from geoworkbench.project.controller import ProjectController
from geoworkbench.services.localization import AppLanguage
from test_masterlog_control_layout import controlled_form


NAMES = {"ru": "Меловая система", "kk": "Бор Әғқң", "en": "Cretaceous system"}


def _fixture(orientation="horizontal"):
    session, template = controlled_form()
    session.current_well.stratigraphy = [
        StratigraphyInterval("period", 140, 160, "K₁", "LEGACY", "System / Period",
                             text_orientation=orientation, name_i18n=NAMES.copy()),
    ]
    session.current_well.cuttings = [
        CuttingsSample("sample", 140, 160, lba_type_id="light", lba_color="БГ", lba_intensity=3),
    ]
    template.columns = [
        MasterlogColumnTemplate("strat", "Stratigraphy", "stratigraphy", 90),
        MasterlogColumnTemplate("lba", "LBA", "lba", 90,
                               properties={"lba_label_orientation": orientation}),
    ]
    return session, template


@pytest.mark.parametrize("language", list(AppLanguage))
@pytest.mark.parametrize("dpi", [72, 96, 144, 300, 600])
@pytest.mark.parametrize("orientation", ["horizontal", "vertical_bottom_to_top", "vertical_top_to_bottom"])
@pytest.mark.parametrize("kind", ["stratigraphy", "lba"])
def test_geology_labels_use_actual_unicode_and_preserve_pdf_dpi_baseline(
    qapp, tmp_path, monkeypatch, language, dpi, orientation, kind
):
    session, template = _fixture(orientation)
    before = deepcopy((session.current_well.stratigraphy, session.current_well.cuttings))
    source_values = session.current_dataset.curve_by_mnemonic("C1").values.copy()
    old_ui_font = QFont(qapp.font())
    calls = []
    original_print_font = renderer.print_font

    def capture(size, *, text):
        font = original_print_font(size, text=text)
        calls.append((size, text, font.families()))
        return font

    monkeypatch.setattr(renderer, "print_font", capture)
    snapshots = []
    expected = ["K₁", NAMES[language.value]] if kind == "stratigraphy" else ["БГ", "ЛБ"]
    try:
        qapp.setFont(QFont("Courier New", 19))
        for index, resolution in enumerate((72, dpi)):
            target = tmp_path / f"labels-{index}.pdf"
            writer = QPdfWriter(str(target))
            writer.setResolution(resolution)
            painter = QPainter(writer)
            painter.scale(resolution / 25.4, resolution / 25.4)
            try:
                if kind == "stratigraphy":
                    renderer._paint_stratigraphy_column(painter, QRectF(0, 0, 90, 80), session, (130, 170), language)
                else:
                    renderer._paint_lba_column(painter, QRectF(0, 0, 90, 80), template.columns[1], session, (130, 170), language)
            finally:
                painter.end()
            with fitz.open(target) as document:
                text = document[0].get_text()
                for value in expected:
                    assert value in text
                assert "LEGACY" not in text
                spans = [span for block in document[0].get_text("dict")["blocks"]
                         if "lines" in block for line in block["lines"] for span in line["spans"]]
                drawings = [(draw["type"], draw["color"], draw["fill"], tuple(draw["rect"]))
                            for draw in document[0].get_drawings()]
                snapshots.append((spans, drawings))
    finally:
        qapp.setFont(old_ui_font)
    assert (session.current_well.stratigraphy, session.current_well.cuttings) == before
    np.testing.assert_array_equal(session.current_dataset.curve_by_mnemonic("C1").values, source_values)
    assert len(calls) == (2 if kind == "stratigraphy" else 4)
    for size, text, families in calls:
        assert size == (5.5 if kind == "stratigraphy" else 5.0)
        assert text in (["K₁\n" + NAMES[language.value]] if kind == "stratigraphy" else expected)
        assert families == list(resolve_unicode_font_profile(text).families)
    baseline, actual = snapshots
    assert [span["text"] for span in actual[0]] == [span["text"] for span in baseline[0]]
    for base_span, actual_span in zip(baseline[0], actual[0]):
        assert actual_span["size"] == pytest.approx(base_span["size"], abs=0.08)
        assert actual_span["bbox"] == pytest.approx(base_span["bbox"], abs=0.3)
    assert len(actual[1]) == len(baseline[1])
    for base_draw, actual_draw in zip(baseline[1], actual[1]):
        assert actual_draw[:3] == base_draw[:3]
        assert actual_draw[3] == pytest.approx(base_draw[3], abs=0.3)


@pytest.mark.parametrize("language", list(AppLanguage))
@pytest.mark.parametrize("page_format", ["A4", "A3", "roll"])
def test_geology_labels_export_after_package_reopen(qapp, tmp_path, language, page_format):
    session, template = _fixture()
    template.page_format = page_format
    package = tmp_path / "labels.geologpkg"
    ProjectController(session=session).save_project(package)
    restored = ProjectController().open_project(package)
    saved = restored.project.masterlog_templates[template.template_id]
    before = deepcopy((saved, restored.current_well.stratigraphy, restored.current_well.cuttings))
    source_values = restored.current_dataset.curve_by_mnemonic("C1").values.copy()
    target = renderer.export_masterlog_pdf(
        saved, restored, tmp_path / "labels.pdf", settings=MasterlogOutputSettings(130, 170, language),
    )
    with fitz.open(target) as document:
        text = "".join(page.get_text() for page in document)
        for value in ("K₁", NAMES[language.value], "БГ", "ЛБ"):
            assert value in text
        assert "LEGACY" not in text
    assert (saved, restored.current_well.stratigraphy, restored.current_well.cuttings) == before
    np.testing.assert_array_equal(restored.current_dataset.curve_by_mnemonic("C1").values, source_values)
