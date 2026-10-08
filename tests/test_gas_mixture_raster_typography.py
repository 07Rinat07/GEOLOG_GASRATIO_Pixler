from base64 import b64decode
from copy import deepcopy
from dataclasses import replace
from io import BytesIO

from PIL import Image
import pytest
from PySide6.QtGui import QFont, QFontMetricsF, QPainter

from geoworkbench.printing import gas_mixture_ramp_report as ramp
from geoworkbench.printing.report_visual_system import modern_oilfield_report_profile
from geoworkbench.services.localization import AppLanguage
from test_gas_mixture_ramp_report import _session


@pytest.mark.parametrize("language", list(AppLanguage))
@pytest.mark.parametrize("profile_kind", ["default", "custom", "large"])
def test_ramp_raster_uses_profile_roles_and_fits_full_unicode_labels(qapp, monkeypatch, language, profile_kind):
    visual = modern_oilfield_report_profile()
    if profile_kind == "custom":
        visual = replace(visual, typography=replace(
            visual.typography, title_pt=25, caption_pt=9, table_pt=11, subtitle_pt=12,
        ))
    elif profile_kind == "large":
        visual = replace(visual, typography=replace(
            visual.typography, title_pt=36, caption_pt=36, table_pt=36, subtitle_pt=36,
        ))
    monkeypatch.setattr(ramp, "modern_oilfield_report_profile", lambda: visual)
    report = replace(ramp.build_gas_mixture_ramp_report(_session()), time_label="Уақыт / Время / Time, ms")
    before = deepcopy(report)
    requests = []
    drawn = []
    original_font = ramp.print_font

    def capture_font(size, *, text, bold=False):
        font = original_font(size, text=text, bold=bold)
        requests.append((size, text, bold, font.families()))
        return font

    class CapturePainter(QPainter):
        def drawText(self, rect, flags, text):
            font = self.font()
            metrics = QFontMetricsF(font, self.device())
            assert metrics.horizontalAdvance(text) <= rect.width()
            assert metrics.height() <= rect.height()
            drawn.append((text, font))
            super().drawText(rect, flags, text)

    monkeypatch.setattr(ramp, "print_font", capture_font)
    monkeypatch.setattr(ramp, "QPainter", CapturePainter)
    old_ui_font = qapp.font()
    qapp.setFont(QFont("Courier New", 19))
    try:
        uri = ramp._chart_data_uri(report, language)
    finally:
        qapp.setFont(old_ui_font)
    assert Image.open(BytesIO(b64decode(uri.split(",", 1)[1]))).size == (1500, 650)
    typography = visual.typography
    assert [request[0] for request in requests] == (
        [typography.title_pt] + [typography.caption_pt] * 13
        + [typography.table_pt] * 5 + [typography.subtitle_pt]
    )
    assert [request[1] for request in requests] == [text for text, _ in drawn]
    assert requests[0][1] == ramp._labels(language)["chart"]
    assert requests[0][2] is True
    assert requests[-1][1] == report.time_label
    assert [text for text, _ in drawn[-6:-1]] == [name for name, _ in report.series]
    for (size, text, bold, families), (_, font) in zip(requests, drawn, strict=True):
        assert font.families() == families
        assert font.bold() == bold
        assert 1.0 <= font.pointSizeF() <= size
        assert QFontMetricsF(font).inFontUcs4(ord(text[0]))
    if profile_kind == "large":
        assert any(font.pointSizeF() < size for (size, *_), (_, font) in zip(requests, drawn, strict=True))
    assert report == before
