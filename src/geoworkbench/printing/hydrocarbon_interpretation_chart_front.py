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
    *,
    print_layout: bool = False,
) -> str:
    """Insert the whole-well chart before the first tabular report section."""

    base = hydrocarbon_interpretation_html(report, language)
    from geoworkbench.services.hydrocarbon_interpretation_gas_html import (
        inject_interval_gas_statistics_html,
    )

    base = inject_interval_gas_statistics_html(base, report, dataset, language)
    uri = hydrocarbon_interpretation_chart_data_uri(report, dataset, language)
    if not uri:
        return base
    labels = _labels(language)
    block = _chart_block(uri, labels, print_layout=print_layout)
    marker = "<h2>"
    if marker in base:
        return base.replace(marker, block + marker, 1)
    return base.replace("</body>", block + "</body>")


def _chart_block(
    uri: str,
    labels: dict[str, str],
    *,
    print_layout: bool,
) -> str:
    if print_layout:
        section_style = (
            "page-break-before: always; page-break-after: always; "
            "page-break-inside: avoid; margin: 0;"
        )
        heading_style = "margin: 0 0 6px 0;"
        note_style = "margin: 0 0 8px 0;"
        wrapper_style = (
            "width: 100%; text-align: center; page-break-inside: avoid;"
        )
        image_style = (
            "display: block; width: 86%; max-width: 880px; height: auto; "
            "margin: 0 auto; page-break-inside: avoid;"
        )
    else:
        section_style = ""
        heading_style = ""
        note_style = ""
        wrapper_style = "width: 100%; text-align: center;"
        image_style = (
            "display:block; width:100%; max-width:1050px; height:auto; "
            "margin:0 auto;"
        )

    return (
        f"<div class='interpretation-curves' style='{section_style}'>"
        f"<h2 style='{heading_style}'>{escape(labels['title'])}</h2>"
        f"<p style='{note_style}'><small>{escape(labels['note'])}</small></p>"
        f"<div style='{wrapper_style}'>"
        f'<img alt="{escape(labels["title"])}" style="{image_style}" '
        f'src="{uri}" />'
        "</div>"
        "</div>"
    )


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
