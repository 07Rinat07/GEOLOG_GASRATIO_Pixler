from copy import deepcopy

import fitz
import numpy as np
import pytest
from PySide6.QtCore import QRectF
from PySide6.QtGui import QFont, QPainter, QPdfWriter

from geoworkbench.domain.models import (
    Dataset, DatasetKind, DepthDomain, MasterlogColumnTemplate, MasterlogCurveStyle,
    MasterlogTemplate,
)
from geoworkbench.printing import masterlog_renderer as renderer
from geoworkbench.printing.masterlog_output import MasterlogOutputSettings
from geoworkbench.printing.unicode_support import resolve_unicode_font_profile
from geoworkbench.project.controller import ProjectController
from geoworkbench.project.session import ProjectSession
from geoworkbench.services.localization import AppLanguage


TITLES = {"ru": "Газовый каротаж", "kk": "Газ Әғқң", "en": "Gas log"}
UNIT = "м³/кг·µg"
LABEL = f"TG 1–3 ({UNIT})"


def _fixture(language, orientation="horizontal", legend=True):
    dataset = Dataset("log", "Log", DatasetKind.GTI, DepthDomain.MD, np.array([100., 101., 102.]))
    curve = dataset.upsert_curve("VENDOR", np.array([1., 2., 3.]), unit=UNIT)
    bindings = {"TG": curve.metadata.curve_id}
    column = MasterlogColumnTemplate(
        "gas", TITLES[language.value], "curves", 140, ["TG"], show_legend=legend,
        properties={"title_orientation": orientation, "title_position": "center"},
        curve_styles={"TG": MasterlogCurveStyle("#111111", 0.8, "dash_dot")},
    )
    return dataset, bindings, column


@pytest.mark.parametrize("language", list(AppLanguage))
@pytest.mark.parametrize("dpi", [72, 96, 144, 300, 600])
@pytest.mark.parametrize("orientation", ["horizontal", "vertical_bottom_to_top", "vertical_top_to_bottom"])
@pytest.mark.parametrize("legend", [False, True])
def test_heading_and_curve_label_unicode_pdf_keep_orientation_and_dpi_baseline(
    qapp, tmp_path, monkeypatch, language, dpi, orientation, legend
):
    dataset, bindings, column = _fixture(language, orientation, legend)
    before = deepcopy(column)
    source_values = dataset.curve_by_mnemonic("VENDOR").values.copy()
    source_metadata = deepcopy(dataset.curve_by_mnemonic("VENDOR").metadata)
    old_ui_font = QFont(qapp.font())
    resolved = []
    original_print_font = renderer.print_font

    def capture(size, *, text):
        font = original_print_font(size, text=text)
        resolved.append((size, text, font.families()))
        return font

    monkeypatch.setattr(renderer, "print_font", capture)
    pdf_spans = []
    try:
        qapp.setFont(QFont("Courier New", 19))
        for index, resolution in enumerate((72, dpi)):
            target = tmp_path / f"heading-{index}.pdf"
            writer = QPdfWriter(str(target))
            writer.setResolution(resolution)
            painter = QPainter(writer)
            painter.scale(resolution / 25.4, resolution / 25.4)
            try:
                renderer._paint_column_heading(
                    painter, QRectF(0, 0, 140, 80), column, dataset, bindings,
                )
            finally:
                painter.end()
            with fitz.open(target) as document:
                text = document[0].get_text()
                assert TITLES[language.value] in text
                assert (LABEL in text) == legend
                spans = [span for block in document[0].get_text("dict")["blocks"]
                         if "lines" in block for line in block["lines"] for span in line["spans"]]
                assert spans
                pdf_spans.append(spans)
                if legend:
                    assert any(draw["dashes"] != "[] 0" for draw in document[0].get_drawings()
                               if draw["color"])
    finally:
        qapp.setFont(old_ui_font)
    assert column == before
    assert dataset.curve_by_mnemonic("VENDOR").metadata == source_metadata
    np.testing.assert_array_equal(dataset.curve_by_mnemonic("VENDOR").values, source_values)
    assert len(resolved) == (4 if legend else 2)
    for size, text, families in resolved:
        assert (size, text) in ((renderer.modern_oilfield_report_profile().typography.table_pt, column.title),
                                (renderer.modern_oilfield_report_profile().typography.caption_pt, LABEL))
        assert families == list(resolve_unicode_font_profile(text).families)
    assert [span["text"] for span in pdf_spans[0]] == [span["text"] for span in pdf_spans[1]]
    for baseline, actual in zip(*pdf_spans):
        assert actual["size"] == pytest.approx(baseline["size"], abs=0.08)
        assert actual["bbox"] == pytest.approx(baseline["bbox"], abs=0.3)


@pytest.mark.parametrize("language", list(AppLanguage))
@pytest.mark.parametrize("page_format", ["A4", "A3", "roll"])
def test_heading_and_bound_unicode_unit_export_after_reopen(qapp, tmp_path, language, page_format):
    dataset, bindings, column = _fixture(language)
    session = ProjectSession()
    session.add_dataset(dataset, "Well")
    template = MasterlogTemplate(
        "form", "Form", page_format=page_format, columns=[column],
        properties={"dataset_curve_bindings": {"log": bindings}},
    )
    session.project.masterlog_templates["form"] = template
    package = tmp_path / "headings.geologpkg"
    ProjectController(session=session).save_project(package)
    restored = ProjectController().open_project(package)
    saved = restored.project.masterlog_templates["form"]
    before = deepcopy(saved)
    source_values = restored.current_dataset.curve_by_mnemonic("VENDOR").values.copy()
    source_metadata = deepcopy(restored.current_dataset.curve_by_mnemonic("VENDOR").metadata)
    target = renderer.export_masterlog_pdf(
        saved, restored, tmp_path / "masterlog.pdf",
        settings=MasterlogOutputSettings(100, 102, language),
    )
    with fitz.open(target) as document:
        text = "".join(page.get_text() for page in document)
        assert TITLES[language.value] in text
        assert LABEL in text
    assert saved == before
    assert restored.current_dataset.curve_by_mnemonic("VENDOR").metadata == source_metadata
    np.testing.assert_array_equal(restored.current_dataset.curve_by_mnemonic("VENDOR").values, source_values)
