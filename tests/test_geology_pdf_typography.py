from dataclasses import replace

import fitz
import numpy as np
import pytest

from geoworkbench.printing import interpretation_report as geology
from geoworkbench.printing.report_visual_system import modern_oilfield_report_profile
from geoworkbench.services.localization import AppLanguage
from test_interpretation_report import _session


@pytest.mark.parametrize("language", list(AppLanguage))
@pytest.mark.parametrize("custom", [False, True])
def test_geology_pdf_preserves_explicit_profile_font_sizes(qapp, tmp_path, monkeypatch, language, custom):
    visual = modern_oilfield_report_profile()
    if custom:
        visual = replace(visual, typography=replace(
            visual.typography, title_pt=23, section_pt=15, body_pt=11, table_pt=8,
        ))
    monkeypatch.setattr(geology, "modern_oilfield_report_profile", lambda: visual)
    session = _session()
    assert session.current_dataset is not None
    values = {key: curve.values.copy() for key, curve in session.current_dataset.curves.items()}
    report = geology.build_interpretation_report(session)
    destination = geology.export_interpretation_report_pdf(report, tmp_path / "geology.pdf", language=language)
    labels = geology._LABELS[language]
    with fitz.open(destination) as document:
        spans = [
            span for page in document for block in page.get_text("dict")["blocks"]
            if "lines" in block for line in block["lines"] for span in line["spans"]
        ]
        text = "\n".join(page.get_text() for page in document)
        for label, size in (
            (labels["title"], visual.typography.title_pt),
            (labels["sample_section"], visual.typography.section_pt),
            (labels["gas_lba_section"], visual.typography.section_pt),
            (labels["project"] + ":", visual.typography.body_pt),
            ("Manual conclusion", visual.typography.table_pt),
        ):
            assert label in " ".join(text.split())
            matching = []
            for index, span in enumerate(spans):
                if not label.startswith(span["text"]):
                    continue
                candidate = []
                for fragment in spans[index:]:
                    candidate.append(fragment)
                    combined = " ".join(item["text"] for item in candidate)
                    if combined == label:
                        matching = candidate
                        break
                    if not label.startswith(combined):
                        break
                if matching:
                    break
            assert matching, label
            assert all(span["size"] == pytest.approx(size, abs=0.3) for span in matching), matching
        assert report.well_name in text
        assert "Manual conclusion" in text
        assert "Requires correlation" in text
    for key, source in values.items():
        np.testing.assert_array_equal(session.current_dataset.curves[key].values, source)
