from base64 import b64decode
from dataclasses import replace
from io import BytesIO

import numpy as np
from PIL import Image
import pytest
from PySide6.QtGui import QFontMetricsF, QPainter

from geoworkbench.printing import gas_ratio_reference as reference
from geoworkbench.printing.report_visual_system import modern_oilfield_report_profile
from geoworkbench.services.localization import AppLanguage
from test_gas_ratio_reference import _dataset
from test_ratio_reference_physical_dpi import _export


def _profile(kind):
    visual = modern_oilfield_report_profile()
    if kind != "default":
        size = 36 if kind == "large" else 11
        visual = replace(visual, typography=replace(visual.typography,
            title_pt=36 if kind == "large" else 25,
            section_pt=size, body_pt=size, caption_pt=size, footer_pt=size))
    return visual


@pytest.mark.parametrize("language", list(AppLanguage))
@pytest.mark.parametrize("kind", ["default", "custom", "large"])
@pytest.mark.parametrize("partial", [False, True])
def test_reference_png_profile_text_fits_complete_labels_and_empty_states(qapp, monkeypatch, language, kind, partial):
    visual = _profile(kind)
    monkeypatch.setattr(reference, "modern_oilfield_report_profile", lambda: visual)
    dataset = _dataset()
    if partial:
        dataset.curves.pop("BH")
        dataset.curves.pop("C1_C5")
    before = {name: curve.values.copy() for name, curve in dataset.curves.items()}
    drawn = []
    requests = []
    original_text = reference._text

    def capture_text(painter, rect, text, size=None):
        requests.append((rect, text, size))
        original_text(painter, rect, text, size)

    class CapturePainter(QPainter):
        def drawText(self, rect, flags, text):
            metrics = QFontMetricsF(self.font(), self.device())
            assert metrics.horizontalAdvance(text) <= rect.width()
            assert metrics.height() <= rect.height()
            drawn.append(text)
            super().drawText(rect, flags, text)

    monkeypatch.setattr(reference, "_text", capture_text)
    monkeypatch.setattr(reference, "QPainter", CapturePainter)
    uri = reference.ratio_reference_summary_uri(dataset, language)
    assert Image.open(BytesIO(b64decode(uri.split(",", 1)[1]))).size == (1600, 1040)
    assert drawn == [text for _, text, _ in requests]
    assert requests[0][2] == visual.typography.title_pt
    assert next(size for _, text, size in requests if text.startswith("Pixler")) == visual.typography.section_pt
    assert requests[-1][2] == visual.typography.footer_pt
    assert all(size == visual.typography.caption_pt for rect, _, size in requests if rect.height() == 15)
    assert "C1 / ΣHC" in drawn
    assert "C1/C2" in drawn and "C1/C5" in drawn
    if partial:
        assert any(rect.height() == 205 and size is None for rect, _, size in requests)
        assert any(rect.height() == 205 and size == visual.typography.body_pt for rect, _, size in requests)
    for name, curve in dataset.curves.items():
        np.testing.assert_array_equal(curve.values, before[name])


@pytest.mark.parametrize("language", list(AppLanguage))
@pytest.mark.parametrize("kind", ["default", "custom", "large"])
@pytest.mark.parametrize("dpi", [72, 300, 600])
def test_reference_pdf_profile_keeps_complete_text_and_physical_sizes(qapp, tmp_path, monkeypatch, language, kind, dpi):
    visual = _profile(kind)
    monkeypatch.setattr(reference, "modern_oilfield_report_profile", lambda: visual)
    baseline = _export(tmp_path / "baseline.pdf", _dataset(), language, 72, False)
    actual = _export(tmp_path / "actual.pdf", _dataset(), language, dpi, False)
    assert [span["text"] for span in actual] == [span["text"] for span in baseline]
    for expected, span in zip(baseline, actual, strict=True):
        assert span["size"] == pytest.approx(expected["size"], abs=0.3)
        assert span["bbox"] == pytest.approx(expected["bbox"], abs=0.8)
