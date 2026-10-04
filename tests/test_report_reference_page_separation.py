from __future__ import annotations

from PySide6.QtCore import QRectF

from geoworkbench.domain.report_composition import ReportLegendMode
from geoworkbench.printing import hydrocarbon_interpretation_pdf_renderer as renderer
from geoworkbench.printing.hydrocarbon_interpretation_geology_legend import (
    GeologyLegendItem,
    InterpretationGeologyLegend,
)
from geoworkbench.services.localization import AppLanguage


class _PainterProbe:
    def device(self) -> object:
        return object()


class _CanvasProbe:
    def __init__(self) -> None:
        self.content_rect = QRectF(0.0, 0.0, 600.0, 800.0)
        self.painter = _PainterProbe()
        self.y = 0.0
        self.page = 0

    def new_page(self) -> None:
        self.page += 1
        self.y = self.content_rect.top()


def _legend() -> InterpretationGeologyLegend:
    return InterpretationGeologyLegend(
        (
            GeologyLegendItem(
                "lithology",
                "limestone",
                "8",
                "Известняки",
                "#22d3ee",
                "carbonate",
            ),
        )
    )


def test_geology_legend_and_chart_methodology_use_dedicated_pages(monkeypatch) -> None:
    canvas = _CanvasProbe()
    events: list[tuple[str, int]] = []

    monkeypatch.setattr(
        renderer,
        "paginate_geology_legend",
        lambda *args, **kwargs: (_legend(),),
    )
    monkeypatch.setattr(renderer, "geology_legend_height", lambda *args, **kwargs: 120.0)
    monkeypatch.setattr(
        renderer,
        "paint_geology_legend",
        lambda painter, rect, legend, language, **kwargs: events.append(
            ("legend", canvas.page)
        ),
    )
    monkeypatch.setattr(
        renderer,
        "render_report_html",
        lambda report_canvas, html, **kwargs: events.append(
            ("methodology", report_canvas.page)
        ),
    )

    renderer._render_chart_reference_pages(
        canvas,  # type: ignore[arg-type]
        key_html="<h2>Пояснения к графикам</h2>",
        geology_legend=_legend(),
        language=AppLanguage.RU,
        legend_mode=ReportLegendMode.FULL,
    )

    assert events == [("legend", 1), ("methodology", 2)]
    assert events[0][1] != events[1][1]


def test_hidden_geology_legend_does_not_hide_chart_methodology(monkeypatch) -> None:
    canvas = _CanvasProbe()
    events: list[tuple[str, int]] = []

    monkeypatch.setattr(
        renderer,
        "paint_geology_legend",
        lambda *args, **kwargs: events.append(("legend", canvas.page)),
    )
    monkeypatch.setattr(
        renderer,
        "render_report_html",
        lambda report_canvas, html, **kwargs: events.append(
            ("methodology", report_canvas.page)
        ),
    )

    renderer._render_chart_reference_pages(
        canvas,  # type: ignore[arg-type]
        key_html="<h2>Пояснения к графикам</h2>",
        geology_legend=_legend(),
        language=AppLanguage.RU,
        legend_mode=ReportLegendMode.HIDE,
    )

    assert events == [("methodology", 1)]
