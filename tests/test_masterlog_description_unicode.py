from copy import deepcopy

import fitz
import numpy as np
import pytest
from PySide6.QtCore import QRectF
from PySide6.QtGui import QFont, QPainter, QPdfWriter

from geoworkbench.domain.models import CuttingsSample, LithologyInterval, MasterlogColumnTemplate
from geoworkbench.printing import masterlog_renderer as renderer
from geoworkbench.printing.masterlog_output import MasterlogOutputSettings
from geoworkbench.printing.unicode_support import resolve_unicode_font_profile
from geoworkbench.project.controller import ProjectController
from geoworkbench.services.localization import AppLanguage
from test_masterlog_control_layout import controlled_form


DESCRIPTIONS = {
    "ru": "Песчаник мелкозернистый",
    "kk": "Құмтас Әә Ғғ Ққ Ңң Өө Ұұ Үү Һһ Іі",
    "en": "Fine grained sandstone",
}
CONCLUSIONS = {"ru": "Нефтенасыщение", "kk": "Мұнайға қаныққан", "en": "Oil saturation"}


def _session():
    session, template = controlled_form()
    session.current_well.lithology = [
        LithologyInterval("rock", 145, 155, "sandstone", description="LEGACY ROCK",
                          description_i18n=DESCRIPTIONS.copy()),
    ]
    session.current_well.cuttings = [
        CuttingsSample("sample", 145, 155, description="LEGACY SAMPLE",
                       description_i18n={key: f'<p style="text-align:right">{value}</p>'
                                         for key, value in DESCRIPTIONS.items()},
                       analysis_interpretation="LEGACY CONCLUSION",
                       analysis_interpretation_i18n=CONCLUSIONS.copy()),
    ]
    return session, template


@pytest.mark.parametrize("language", list(AppLanguage))
@pytest.mark.parametrize("dpi", [72, 96, 144, 300, 600])
@pytest.mark.parametrize("kind", ["lithology", "cuttings", "interpretation"])
def test_geology_text_pdf_resolves_actual_unicode_and_keeps_dpi_baseline(
    qapp, tmp_path, monkeypatch, language, dpi, kind
):
    session, _ = _session()
    before = deepcopy((session.current_well.lithology, session.current_well.cuttings))
    source_depth = session.current_dataset.depth.copy()
    source_values = session.current_dataset.curve_by_mnemonic("C1").values.copy()
    original_ui_font = QFont(qapp.font())
    resolved = []
    original_print_font = renderer.print_font

    def capture(size, *, text):
        font = original_print_font(size, text=text)
        resolved.append((size, text, font.families()))
        return font

    monkeypatch.setattr(renderer, "print_font", capture)
    spans_by_dpi = []
    try:
        qapp.setFont(QFont("Courier New", 19))
        for index, resolution in enumerate((72, dpi)):
            target = tmp_path / f"description-{index}.pdf"
            writer = QPdfWriter(str(target))
            writer.setResolution(resolution)
            painter = QPainter(writer)
            painter.scale(resolution / 25.4, resolution / 25.4)
            old_font, old_pen = painter.font(), painter.pen()
            try:
                rect = QRectF(0, 0, 170, 70)
                if kind == "lithology":
                    renderer._paint_lithology_descriptions(
                        painter, rect, session, (145, 155), language, {},
                    )
                elif kind == "cuttings":
                    renderer._paint_cuttings_descriptions(
                        painter, rect, session, (145, 155), language,
                    )
                else:
                    renderer._paint_sample_interpretations(
                        painter, rect, session, (145, 155), language,
                    )
                assert painter.font() == old_font
                assert painter.pen() == old_pen
            finally:
                painter.end()
            with fitz.open(target) as document:
                text = document[0].get_text()
                assert DESCRIPTIONS[language.value] in text
                if kind == "interpretation":
                    assert CONCLUSIONS[language.value] in text
                assert "LEGACY" not in text and "<p" not in text
                spans = [span for block in document[0].get_text("dict")["blocks"]
                         if "lines" in block for line in block["lines"] for span in line["spans"]]
                assert spans
                spans_by_dpi.append(spans)
    finally:
        qapp.setFont(original_ui_font)
    assert (session.current_well.lithology, session.current_well.cuttings) == before
    np.testing.assert_array_equal(session.current_dataset.depth, source_depth)
    np.testing.assert_array_equal(session.current_dataset.curve_by_mnemonic("C1").values, source_values)
    assert len(resolved) == 2
    for size, text, families in resolved:
        assert size == (6.0 if kind == "interpretation" else 6.5)
        assert families == list(resolve_unicode_font_profile(text).families)
        assert "<p" not in text
    assert [span["text"] for span in spans_by_dpi[0]] == [span["text"] for span in spans_by_dpi[1]]
    for baseline, actual in zip(*spans_by_dpi):
        assert actual["size"] == pytest.approx(baseline["size"], abs=0.08)
        assert actual["bbox"] == pytest.approx(baseline["bbox"], abs=0.3)


@pytest.mark.parametrize("language", list(AppLanguage))
def test_geology_text_production_export_after_reopen(qapp, tmp_path, language):
    session, template = _session()
    template.columns = [
        MasterlogColumnTemplate("depth", "Depth", "depth", 20),
        MasterlogColumnTemplate("rock", "Rock", "description", 60),
        MasterlogColumnTemplate("sample", "Sample", "cuttings_description", 60),
        MasterlogColumnTemplate("result", "Result", "analysis_interpretation", 60),
    ]
    package = tmp_path / "descriptions.geologpkg"
    ProjectController(session=session).save_project(package)
    restored = ProjectController().open_project(package)
    saved = restored.project.masterlog_templates[template.template_id]
    before_form = deepcopy(saved)
    before_geology = deepcopy((restored.current_well.lithology, restored.current_well.cuttings))
    source_depth = restored.current_dataset.depth.copy()
    source_values = restored.current_dataset.curve_by_mnemonic("C1").values.copy()
    output = renderer.export_masterlog_pdf(
        saved, restored, tmp_path / "masterlog.pdf",
        settings=MasterlogOutputSettings(145, 155, language),
    )
    with fitz.open(output) as document:
        text = "".join(page.get_text() for page in document)
        assert DESCRIPTIONS[language.value] in text
        assert CONCLUSIONS[language.value] in text
        assert "LEGACY" not in text
    assert saved == before_form
    assert (restored.current_well.lithology, restored.current_well.cuttings) == before_geology
    np.testing.assert_array_equal(restored.current_dataset.depth, source_depth)
    np.testing.assert_array_equal(restored.current_dataset.curve_by_mnemonic("C1").values, source_values)
