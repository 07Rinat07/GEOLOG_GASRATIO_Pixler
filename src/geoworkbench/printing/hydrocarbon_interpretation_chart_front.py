from __future__ import annotations

from html import escape

from geoworkbench.domain.depth_interval import scope_dataset
from geoworkbench.domain.models import Dataset
from geoworkbench.domain.report_composition import ReportLayoutProfile, ReportLegendMode
from geoworkbench.domain.report_annotations import ReportAnnotationRecord
from geoworkbench.printing.interpretation_chart_key import interpretation_chart_key_html
from geoworkbench.printing.hydrocarbon_interpretation_chart import (
    hydrocarbon_interpretation_chart_data_uri,
)
from geoworkbench.printing.hydrocarbon_interpretation_geology import (
    InterpretationGeologySnapshot,
)
from geoworkbench.printing.hydrocarbon_interpretation_geology_settings import (
    DEFAULT_INTERPRETATION_GEOLOGY_TRACK_SETTINGS,
    InterpretationGeologyTrackSettings,
)
from geoworkbench.printing.hydrocarbon_interpretation_report_identity import (
    InterpretationReportIdentity,
    inject_report_optional_sections_html,
)
from geoworkbench.printing.hydrocarbon_interpretation_report_range import (
    ReportDepthRange,
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
    geology: InterpretationGeologySnapshot | None = None,
    geology_track_settings: InterpretationGeologyTrackSettings = (
        DEFAULT_INTERPRETATION_GEOLOGY_TRACK_SETTINGS
    ),
    depth_range: ReportDepthRange | None = None,
    legend_mode: ReportLegendMode = ReportLegendMode.FULL,
    layout_profile: ReportLayoutProfile = ReportLayoutProfile.MODERN_OILFIELD,
    identity: InterpretationReportIdentity | None = None,
    annotations: tuple[ReportAnnotationRecord, ...] = (),
) -> str:
    """Insert the whole-well chart before the first tabular report section."""

    depth_range = report.analysis_depth_interval or depth_range
    base = hydrocarbon_interpretation_html(report, language)
    from geoworkbench.services.hydrocarbon_interpretation_gas_html import (
        inject_interval_gas_statistics_html,
    )

    base = inject_interval_gas_statistics_html(base, report, scope_dataset(dataset, report.analysis_depth_interval), language)
    base = inject_report_optional_sections_html(base, identity, language)
    uri = hydrocarbon_interpretation_chart_data_uri(
        report,
        dataset,
        language,
        geology=geology,
        geology_track_settings=geology_track_settings,
        depth_range=depth_range,
        legend_mode=legend_mode,
        annotations=annotations,
    )
    if not uri:
        return base
    labels = _labels(language)
    key_html = (
        ""
        if legend_mode is ReportLegendMode.HIDE
        else interpretation_chart_key_html(
            report,
            scope_dataset(dataset, report.analysis_depth_interval),
            language,
        )
    )
    key_block = (
        (
            "<div class='interpretation-chart-key' "
            "style='page-break-before:always;page-break-after:always;'>"
            + key_html
            + "</div>"
        )
        if print_layout and key_html
        else key_html
    )
    block = key_block + _chart_block(
        uri,
        labels,
        print_layout=print_layout,
        layout_profile=layout_profile,
    )
    marker = "<h2>"
    if marker in base:
        return base.replace(marker, block + marker, 1)
    return base.replace("</body>", block + "</body>")


def _chart_block(
    uri: str,
    labels: dict[str, str],
    *,
    print_layout: bool,
    layout_profile: ReportLayoutProfile = ReportLayoutProfile.MODERN_OILFIELD,
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
        f"<div class='interpretation-curves' data-layout-profile='{layout_profile.value}' "
        f"style='{section_style}'>"
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
                "дорожки по диапазону p5–p95; масштаб предназначен для сопоставления формы."
            ),
        },
        AppLanguage.KK: {
            "title": "Тереңдік бойынша интерпретациялық қисықтар графиктері",
            "note": (
                "Графиктер кестелердің алдында берілген. Әр қисық өз жолында p5–p95 ауқымы "
                "бойынша масштабталған; масштаб пішінді салыстыруға арналған."
            ),
        },
        AppLanguage.EN: {
            "title": "Depth plots of interpretation curves",
            "note": (
                "The plots are shown before the tables. Each curve is scaled within its track "
                "to its p5–p95 range; the scale is intended for shape comparison."
            ),
        },
    }[language]


__all__ = ["hydrocarbon_interpretation_html_with_front_chart"]
