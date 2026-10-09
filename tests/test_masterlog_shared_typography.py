from copy import deepcopy
from dataclasses import replace

import fitz
import numpy as np
import pytest
from PySide6.QtCore import QRectF
from PySide6.QtGui import QPainter, QPdfWriter

from geoworkbench.domain.models import MasterlogColumnTemplate
from geoworkbench.printing import masterlog_renderer as renderer
from geoworkbench.printing.masterlog_output import MasterlogOutputSettings
from geoworkbench.project.controller import ProjectController
from geoworkbench.services.localization import AppLanguage
from test_masterlog_callout_unicode import LABELS, _fixture as callout_fixture, _paint as paint_callout
from test_masterlog_description_unicode import CONCLUSIONS, DESCRIPTIONS, _session
from test_masterlog_geology_label_unicode import NAMES, _fixture as geology_fixture
from test_masterlog_heading_unicode import LABEL, TITLES, _fixture as heading_fixture


KINDS = ["heading", "stratigraphy", "lba", "lithology", "cuttings", "interpretation", "inspection", "symbol"]


def _profile(kind):
    visual = renderer.modern_oilfield_report_profile()
    if kind == "default":
        return visual
    size = 12 if kind == "custom" else 36
    return replace(visual, typography=replace(visual.typography, table_pt=size, caption_pt=size, body_pt=size))


def _case(tmp_path, language, kind):
    if kind == "heading":
        dataset, bindings, column = heading_fixture(language)
        return (lambda p: renderer._paint_column_heading(p, QRectF(0, 0, 140, 80), column, dataset, bindings),
                [TITLES[language.value], LABEL], ["table_pt", "caption_pt"])
    if kind in ("inspection", "symbol"):
        session, template, callout, _ = callout_fixture(tmp_path, language)
        expected = callout.properties["text"] if kind == "inspection" else LABELS[language.value]
        return lambda p: paint_callout(p, session, template, kind), [expected], ["caption_pt"]
    if kind in ("stratigraphy", "lba"):
        session, template = geology_fixture()
        rect = QRectF(0, 0, 90, 80)
        if kind == "stratigraphy":
            return (lambda p: renderer._paint_stratigraphy_column(p, rect, session, (130, 170), language),
                    ["K₁", NAMES[language.value]], ["caption_pt"])
        return (lambda p: renderer._paint_lba_column(p, rect, template.columns[1], session, (130, 170), language),
                ["БГ"], ["caption_pt"])
    session, _ = _session()
    rect = QRectF(0, 0, 170, 70)
    if kind == "lithology":
        def paint(p):
            return renderer._paint_lithology_descriptions(p, rect, session, (145, 155), language, {})
    elif kind == "cuttings":
        def paint(p):
            return renderer._paint_cuttings_descriptions(p, rect, session, (145, 155), language)
    else:
        def paint(p):
            return renderer._paint_sample_interpretations(p, rect, session, (145, 155), language)
    expected = [DESCRIPTIONS[language.value]]
    if kind == "interpretation":
        expected.append(CONCLUSIONS[language.value])
    return paint, expected, ["body_pt"]


@pytest.mark.parametrize("language", list(AppLanguage))
@pytest.mark.parametrize("dpi", [72, 96, 144, 300, 600])
@pytest.mark.parametrize("profile", ["default", "custom", "large"])
@pytest.mark.parametrize("kind", KINDS)
def test_all_masterlog_default_roles_follow_profile_in_real_pdf(qapp, tmp_path, monkeypatch, language, dpi, profile, kind):
    visual = _profile(profile)
    monkeypatch.setattr(renderer, "modern_oilfield_report_profile", lambda: visual)
    paint, expected, roles = _case(tmp_path, language, kind)
    calls = []
    original = renderer.print_font

    def capture(size, *, text):
        calls.append((size, text))
        return original(size, text=text)

    monkeypatch.setattr(renderer, "print_font", capture)
    snapshots = []
    for index, resolution in enumerate((72, dpi)):
        writer = QPdfWriter(str(tmp_path / f"profile-{index}.pdf"))
        writer.setResolution(resolution)
        painter = QPainter(writer)
        painter.scale(resolution / 25.4, resolution / 25.4)
        try:
            paint(painter)
        finally:
            painter.end()
        with fitz.open(tmp_path / f"profile-{index}.pdf") as document:
            page = document[0]
            text = " ".join(page.get_text().split())
            for value in expected:
                assert " ".join(value.split()) in text
            spans = [span for block in page.get_text("dict")["blocks"] if "lines" in block
                     for line in block["lines"] for span in line["spans"]]
            assert spans
            for span in spans:
                assert span["bbox"][0] >= -0.3 and span["bbox"][1] >= -0.3
                assert span["bbox"][2] <= 180 * 72 / 25.4 + 0.3
                assert span["bbox"][3] <= 80 * 72 / 25.4 + 0.3
            snapshots.append(spans)
    assert calls
    assert {size for size, _ in calls} == {getattr(visual.typography, role) for role in roles}
    assert [s["text"] for s in snapshots[0]] == [s["text"] for s in snapshots[1]]
    for baseline, actual in zip(*snapshots):
        assert actual["size"] == pytest.approx(baseline["size"], abs=0.08)
        assert actual["bbox"] == pytest.approx(baseline["bbox"], abs=0.3)


@pytest.mark.parametrize("language", list(AppLanguage))
@pytest.mark.parametrize("page_format", ["A4", "A3", "roll"])
@pytest.mark.parametrize("profile", ["default", "custom"])
def test_masterlog_profile_export_after_reopen_keeps_form_and_source(qapp, tmp_path, monkeypatch, language, page_format, profile):
    visual = _profile(profile)
    monkeypatch.setattr(renderer, "modern_oilfield_report_profile", lambda: visual)
    session, template = _session()
    template.page_format = page_format
    template.columns = [
        MasterlogColumnTemplate("depth", "Depth", "depth", 20),
        MasterlogColumnTemplate("rock", "Rock", "description", 60),
        MasterlogColumnTemplate("sample", "Sample", "cuttings_description", 60),
        MasterlogColumnTemplate("result", "Result", "analysis_interpretation", 60),
    ]
    package = tmp_path / "profile.geologpkg"
    ProjectController(session=session).save_project(package)
    restored = ProjectController().open_project(package)
    saved = restored.project.masterlog_templates[template.template_id]
    before = deepcopy((saved, restored.current_well.lithology, restored.current_well.cuttings))
    source = restored.current_dataset.curve_by_mnemonic("C1").values.copy()
    output = renderer.export_masterlog_pdf(saved, restored, tmp_path / "masterlog.pdf",
                                          settings=MasterlogOutputSettings(145, 155, language))
    with fitz.open(output) as document:
        text = " ".join(" ".join(page.get_text() for page in document).split())
        assert DESCRIPTIONS[language.value] in text
        assert CONCLUSIONS[language.value] in text
        assert "LEGACY" not in text
    assert (saved, restored.current_well.lithology, restored.current_well.cuttings) == before
    np.testing.assert_array_equal(restored.current_dataset.curve_by_mnemonic("C1").values, source)
