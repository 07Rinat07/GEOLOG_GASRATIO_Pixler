from __future__ import annotations

from html import escape

from geoworkbench.domain.models import Dataset
from geoworkbench.printing.hydrocarbon_interpretation_chart import (
    hydrocarbon_interpretation_chart_data_uri,
)
from geoworkbench.services.hydrocarbon_interpretation import (
    HydrocarbonInterpretationReport,
    hydrocarbon_interpretation_html,
)
from geoworkbench.services.localization import AppLanguage


def hydrocarbon_interpretation_html_with_front_chart(
    report: HydrocarbonInterpretationReport,
    dataset: Dataset,
    language: AppLanguage = AppLanguage.RU,
) -> str:
    """Insert the whole-well chart before the first tabular report section."""

    base = hydrocarbon_interpretation_html(report, language)
    uri = hydrocarbon_interpretation_chart_data_uri(report, dataset, language)
    if not uri:
        return base
    labels = _labels(language)
    block = (
        "<section class='interpretation-curves'>"
        f"<h2>{escape(labels['title'])}</h2>"
        f"<p><small>{escape(labels['note'])}</small></p>"
        f'<img alt="{escape(labels["title"])}" width="1050" height="650" '
        f'src="{uri}" />'
        "</section>"
    )
    marker = "<h2>"
    if marker in base:
        return base.replace(marker, block + marker, 1)
    return base.replace("</body>", block + "</body>")


def _labels(language: AppLanguage) -> dict[str, str]:
    return {
        AppLanguage.RU: {
            "title": "Графики интерпретационных кривых по глубине",
            "note": (
                "Графики приведены перед таблицами. Каждая кривая масштабирована внутри своей "
                "дорожки по диапазону p1–p99; масштаб предназначен для сопоставления формы."
            ),
        },
        AppLanguage.KK: {
            "title": "Тереңдік бойынша интерпретациялық қисықтар графиктері",
            "note": (
                "Графиктер кестелердің алдында берілген. Әр қисық өз жолында p1–p99 ауқымы "
                "бойынша масштабталған; масштаб пішінді салыстыруға арналған."
            ),
        },
        AppLanguage.EN: {
            "title": "Depth plots of interpretation curves",
            "note": (
                "The plots are shown before the tables. Each curve is scaled within its track "
                "to its p1–p99 range; the scale is intended for shape comparison."
            ),
        },
    }[language]


__all__ = ["hydrocarbon_interpretation_html_with_front_chart"]
