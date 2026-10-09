from base64 import b64decode
from io import BytesIO

import fitz
import numpy as np
from PIL import Image
import pytest
from PySide6.QtCore import Qt
from PySide6.QtGui import QPainter

from geoworkbench.printing import gas_ratio_reference as reference
from geoworkbench.printing.report_visual_system import modern_oilfield_report_profile
from geoworkbench.services.localization import AppLanguage
from test_gas_ratio_reference import _dataset
from test_ratio_reference_physical_dpi import _export


def _six_depths():
    dataset = _dataset()
    dataset.depth = np.arange(100.0, 106.0)
    for curve in dataset.curves.values():
        curve.values = np.linspace(curve.values[0], curve.values[-1], 6)
    return dataset


@pytest.mark.parametrize("language", list(AppLanguage))
@pytest.mark.parametrize("grayscale", [False, True])
def test_reference_depth_keys_remain_distinct_in_monochrome_png(qapp, monkeypatch, language, grayscale):
    visual = modern_oilfield_report_profile(grayscale=grayscale)
    monkeypatch.setattr(reference, "modern_oilfield_report_profile", lambda: visual)
    dataset = _six_depths()
    before = {name: curve.values.copy() for name, curve in dataset.curves.items()}
    markers, profiles = [], []
    original_marker = reference._depth_marker

    def capture_marker(painter, center, index, radius=2.0):
        markers.append((center, index, radius))
        original_marker(painter, center, index, radius)

    class CapturePainter(QPainter):
        def drawRect(self, rect):
            assert self.brush().style() == Qt.BrushStyle.NoBrush
            super().drawRect(rect)

        def drawPath(self, path):
            if self.pen().style() != Qt.PenStyle.NoPen:
                profiles.append((self.pen(), path))
            else:
                assert self.brush().style() == Qt.BrushStyle.SolidPattern
            super().drawPath(path)

    monkeypatch.setattr(reference, "_depth_marker", capture_marker)
    monkeypatch.setattr(reference, "QPainter", CapturePainter)
    uri = reference.ratio_reference_summary_uri(dataset, language)
    pixels = np.asarray(Image.open(BytesIO(b64decode(uri.split(",", 1)[1]))).convert("L"))
    assert len(markers) == 48
    assert len(profiles) == 6
    assert len({pen.style() for pen, _ in profiles}) == 6
    assert len({tuple(pen.dashPattern()) for pen, _ in profiles}) == 6
    signatures = []
    for index in range(6):
        center = round((82.5 + 150 * index) * 1.6)
        signature = pixels[517:529, center - 6:center + 6] < 220
        assert np.count_nonzero(signature) > 5
        assert all(not np.array_equal(signature, other) for other in signatures)
        signatures.append(signature)
    # Every paired observation keeps its original ratio/fraction coordinates.
    for plot_index, name in enumerate(("BH", "CH")):
        x, fraction, _depth = reference.reference_pairs(dataset, name)
        maximum = max(1.0, float(x.max()) * 1.05)
        for row, (center, index, radius) in enumerate(markers[plot_index * 6:plot_index * 6 + 6]):
            assert index == row and radius == 2
            assert center.x() == pytest.approx(65 + plot_index * 490 + x[row] / maximum * 395)
            assert center.y() == pytest.approx(285 - fraction[row] * 205)
    for row, (pen, path) in enumerate(profiles):
        assert pen.color().name() == reference._DEPTH_COLORS[row]
        assert path.elementCount() == 4
        for index, name in enumerate(("C1_C2", "C1_C3", "C1_C4", "C1_C5")):
            point = path.elementAt(index)
            assert point.x == pytest.approx(65 + index / 3 * 610)
            assert point.y == pytest.approx(590 - np.log10(dataset.curves[name].values[row]) / 3 * 205)
    for name, curve in dataset.curves.items():
        np.testing.assert_array_equal(curve.values, before[name])


@pytest.mark.parametrize("language", list(AppLanguage))
@pytest.mark.parametrize("dpi", [72, 300, 600])
def test_reference_pdf_has_filled_depth_markers_and_distinct_vector_line_keys(qapp, tmp_path, language, dpi):
    destination = tmp_path / "depth-keys.pdf"
    _export(destination, _six_depths(), language, dpi, False)
    with fitz.open(destination) as pdf:
        drawings = pdf[0].get_drawings()
    assert len([drawing for drawing in drawings if drawing["fill"] is not None]) >= 49
    assert len([drawing for drawing in drawings if drawing["fill"] is not None and drawing["rect"].get_area() > 20]) == 1
    depth_strokes = [drawing for drawing in drawings if drawing["color"] is not None
                     and drawing["width"] == pytest.approx(1.05, abs=0.01)]
    assert len({drawing["dashes"] for drawing in depth_strokes}) == 6
