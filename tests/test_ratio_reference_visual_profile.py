from base64 import b64decode
from dataclasses import replace
from io import BytesIO

import fitz
import numpy as np
from PIL import Image
import pytest

from geoworkbench.printing import gas_ratio_reference as reference
from geoworkbench.printing.report_visual_system import modern_oilfield_report_profile
from geoworkbench.services.localization import AppLanguage
from test_gas_ratio_reference import _dataset
from test_ratio_reference_physical_dpi import _export


def _profile(kind):
    visual = modern_oilfield_report_profile(grayscale=kind == "grayscale")
    if kind == "custom":
        visual = replace(visual, palette=replace(visual.palette,
            page="#fff8ed", text="#281846", border="#b46622", border_strong="#715222"))
    return visual


def _rgb(colour):
    return tuple(int(colour[index:index + 2], 16) for index in (1, 3, 5))


@pytest.mark.parametrize("language", list(AppLanguage))
@pytest.mark.parametrize("kind", ["default", "grayscale", "custom"])
def test_ratio_reference_png_uses_shared_neutral_palette_and_keeps_depth_colours(qapp, monkeypatch, language, kind):
    visual = _profile(kind)
    monkeypatch.setattr(reference, "modern_oilfield_report_profile", lambda: visual)
    dataset = _dataset()
    before = {name: curve.values.copy() for name, curve in dataset.curves.items()}
    uri = reference.ratio_reference_summary_uri(dataset, language)
    pixels = np.asarray(Image.open(BytesIO(b64decode(uri.split(",", 1)[1]))).convert("RGB"))
    assert pixels.shape == (1040, 1600, 3)
    for colour in (visual.palette.page, visual.palette.text, visual.palette.border_strong, *reference._DEPTH_COLORS):
        assert np.count_nonzero(np.all(pixels == _rgb(colour), axis=2)) > 10
    for name, curve in dataset.curves.items():
        np.testing.assert_array_equal(curve.values, before[name])


@pytest.mark.parametrize("language", list(AppLanguage))
@pytest.mark.parametrize("kind", ["grayscale", "custom"])
@pytest.mark.parametrize("dpi", [72, 300, 600])
def test_ratio_reference_pdf_uses_shared_text_background_and_grid(qapp, tmp_path, monkeypatch, language, kind, dpi):
    visual = _profile(kind)
    monkeypatch.setattr(reference, "modern_oilfield_report_profile", lambda: visual)
    destination = tmp_path / "reference.pdf"
    spans = _export(destination, _dataset(), language, dpi, False)
    text_colour = int(visual.palette.text[1:], 16)
    assert all(span["color"] == text_colour for span in spans)
    with fitz.open(destination) as pdf:
        drawings = pdf[0].get_drawings()
    def contains_colour(values, colour):
        expected = tuple(channel / 255 for channel in _rgb(colour))
        return any(value == pytest.approx(expected, abs=0.001) for value in values if value is not None)
    fills = [drawing["fill"] for drawing in drawings]
    strokes = [drawing["color"] for drawing in drawings]
    assert contains_colour(fills, visual.palette.page)
    assert contains_colour(strokes, visual.palette.border)
    assert contains_colour(strokes, visual.palette.border_strong)
    for colour in reference._DEPTH_COLORS:
        assert contains_colour(strokes, colour)
