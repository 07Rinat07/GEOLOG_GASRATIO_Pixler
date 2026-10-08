from base64 import b64decode
from copy import deepcopy
from io import BytesIO

import numpy as np
from PIL import Image
import pytest
from PySide6.QtCore import Qt
from PySide6.QtGui import QPainter, QPainterPath

from geoworkbench.printing import gas_mixture_ramp_report as ramp
from geoworkbench.printing.report_visual_system import modern_oilfield_report_profile
from geoworkbench.services.localization import AppLanguage
from test_gas_mixture_ramp_report import _session


@pytest.mark.parametrize("language", list(AppLanguage))
@pytest.mark.parametrize("grayscale", [False, True])
def test_ramp_curves_and_monochrome_legend_share_distinct_line_patterns(qapp, monkeypatch, language, grayscale):
    profile = modern_oilfield_report_profile(grayscale=grayscale)
    monkeypatch.setattr(ramp, "modern_oilfield_report_profile", lambda: profile)
    session = _session()
    report = ramp.build_gas_mixture_ramp_report(session)
    before = deepcopy(report)
    curves = []
    legends = []

    class CapturePainter(QPainter):
        def drawPath(self, path):
            curves.append((self.pen(), QPainterPath(path)))
            super().drawPath(path)

        def drawLine(self, line):
            if line.y1() == 590.0:
                legends.append(self.pen())
            super().drawLine(line)

    monkeypatch.setattr(ramp, "QPainter", CapturePainter)
    uri = ramp._chart_data_uri(report, language)
    image = Image.open(BytesIO(b64decode(uri.split(",", 1)[1]))).convert("L")
    pixels = np.asarray(image)
    assert image.size == (1500, 650)
    expected = [Qt.PenStyle.SolidLine, Qt.PenStyle.DashLine, Qt.PenStyle.DotLine,
                Qt.PenStyle.DashDotLine, Qt.PenStyle.DashDotDotLine]
    assert [pen.style() for pen, _ in curves] == expected
    assert [pen.style() for pen in legends] == expected
    signatures = []
    x = np.asarray(report.time_values)
    all_values = np.concatenate([np.asarray(values) for _, values in report.series])
    y_max = max(1.0, float(np.max(np.log10(1.0 + all_values))))
    for index, ((name, values), (pen, path), legend) in enumerate(zip(report.series, curves, legends, strict=True)):
        assert pen.color().name() == ramp._COLORS[name]
        assert legend == pen
        assert path.elementCount() == len(values)
        for point_index, value in enumerate(values):
            point = path.elementAt(point_index)
            assert point.x == pytest.approx(90 + (x[point_index] - x.min()) / (x.max() - x.min()) * 1320)
            assert point.y == pytest.approx(550 - np.log10(1 + value) / y_max * 480)
        left = 110 + 135 * index
        signature = pixels[590, left:left + 65] < 220
        assert np.count_nonzero(signature) > 5
        signatures.append(signature)
    for index, signature in enumerate(signatures):
        assert all(not np.array_equal(signature, other) for other in signatures[index + 1:])
    assert report == before
