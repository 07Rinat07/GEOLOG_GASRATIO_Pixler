"""Localized, evidence-first HTML for optional standard-versus-OPUS analytics.

No recalculation, inferred measurements, generic warning panels or schema edits.
Reason codes and numerics come exclusively from MethodComparisonInterval v1.
"""

from __future__ import annotations

from html import escape
from math import isfinite

from geoworkbench.services.interpretation_method_comparison import (
    MethodComparisonInterval,
    MethodComparisonStatus,
)
from geoworkbench.services.localization import AppLanguage


_HEADINGS: dict[str, dict[AppLanguage, str]] = {
    "title": {
        AppLanguage.RU: "Сопоставление стандартного метода и ОПУС",
        AppLanguage.KK: "Стандартты әдіс пен ОПУС нәтижелерін салыстыру",
        AppLanguage.EN: "Standard and OPUS method comparison",
    },
    "intro": {
        AppLanguage.RU: "Статусы отражают согласованность расчётных признаков, а не доказанную фазу или продуктивность пласта.",
        AppLanguage.KK: "Мәртебелер есептелген белгілердің сәйкестігін көрсетеді, қабат флюидінің фазасын не өнімділігін дәлелдемейді.",
        AppLanguage.EN: "Statuses describe agreement between calculated indicators, not proof of formation fluid phase or productivity.",
    },
    "standard": {
        AppLanguage.RU: "Стандартный метод, глубина",
        AppLanguage.KK: "Стандартты әдіс, тереңдік",
        AppLanguage.EN: "Standard method depth",
    },
    "opus": {
        AppLanguage.RU: "ОПУС, глубина",
        AppLanguage.KK: "ОПУС, тереңдік",
        AppLanguage.EN: "OPUS depth",
    },
    "status": {
        AppLanguage.RU: "Результат сопоставления",
        AppLanguage.KK: "Салыстыру нәтижесі",
        AppLanguage.EN: "Comparison result",
    },
    "reason": {
        AppLanguage.RU: "Основание результата",
        AppLanguage.KK: "Нәтиженің негіздемесі",
        AppLanguage.EN: "Reason for result",
    },
    "measurements": {
        AppLanguage.RU: "Проверяемые показатели",
        AppLanguage.KK: "Тексерілетін көрсеткіштер",
        AppLanguage.EN: "Supporting measurements",
    },
    "none": {
        AppLanguage.RU: "Сопоставимые интервалы не представлены.",
        AppLanguage.KK: "Салыстыруға арналған аралықтар жоқ.",
        AppLanguage.EN: "No intervals available for comparison.",
    },
    "overlap": {
        AppLanguage.RU: "Перекрытие",
        AppLanguage.KK: "Қабаттасу",
        AppLanguage.EN: "Overlap",
    },
    "coverage": {
        AppLanguage.RU: "покрытие (стандарт / ОПУС)",
        AppLanguage.KK: "қамту (стандарт / ОПУС)",
        AppLanguage.EN: "coverage (standard / OPUS)",
    },
    "wetness": {
        AppLanguage.RU: "Wetness robust-z",
        AppLanguage.KK: "Wetness robust-z",
        AppLanguage.EN: "Wetness robust-z",
    },
    "pixler": {
        AppLanguage.RU: "Pixler C1/C2",
        AppLanguage.KK: "Pixler C1/C2",
        AppLanguage.EN: "Pixler C1/C2",
    },
    "class": {
        AppLanguage.RU: "Класс ОПУС",
        AppLanguage.KK: "ОПУС класы",
        AppLanguage.EN: "OPUS class",
    },
    "support": {
        AppLanguage.RU: "Поддержка класса ОПУС",
        AppLanguage.KK: "ОПУС класын қолдау",
        AppLanguage.EN: "OPUS class support",
    },
    "valid": {
        AppLanguage.RU: "Валидные строки ОПУС",
        AppLanguage.KK: "ОПУС жарамды жолдары",
        AppLanguage.EN: "OPUS valid rows",
    },
}


_STATUSES: dict[MethodComparisonStatus, dict[AppLanguage, str]] = {
    MethodComparisonStatus.AGREEMENT: {
        AppLanguage.RU: "Признаки согласуются",
        AppLanguage.KK: "Белгілер сәйкес келеді",
        AppLanguage.EN: "Indicators agree",
    },
    MethodComparisonStatus.DISAGREEMENT: {
        AppLanguage.RU: "Признаки расходятся",
        AppLanguage.KK: "Белгілер сәйкес келмейді",
        AppLanguage.EN: "Indicators disagree",
    },
    MethodComparisonStatus.INSUFFICIENT: {
        AppLanguage.RU: "Недостаточно данных для сравнения",
        AppLanguage.KK: "Салыстыру үшін дерек жеткіліксіз",
        AppLanguage.EN: "Insufficient data for comparison",
    },
}


_REASONS: dict[str, dict[AppLanguage, str]] = {
    "bounded_phase_agreement": {
        AppLanguage.RU: "При достаточном перекрытии оба метода дают одинаковое направление признаков: газовая либо жидкая УВ-фаза.",
        AppLanguage.KK: "Аралықтар жеткілікті қабаттасқанда екі әдіс те бір бағыттағы белгілерді көрсетеді: газдық немесе сұйық КС фазасы.",
        AppLanguage.EN: "With sufficient depth overlap, both methods indicate the same broad gas or liquid hydrocarbon family.",
    },
    "bounded_phase_disagreement": {
        AppLanguage.RU: "При достаточном перекрытии стандартный метод и ОПУС указывают на разные направления признаков: газ против жидкой УВ-фазы.",
        AppLanguage.KK: "Аралықтар жеткілікті қабаттасқанда стандартты әдіс пен ОПУС белгілері алшақтайды: газдық және сұйық КС фазалары.",
        AppLanguage.EN: "Despite sufficient depth overlap, the methods indicate different broad families: gas versus liquid hydrocarbons.",
    },
    "no_opus_depth_overlap": {
        AppLanguage.RU: "Для стандартного интервала нет пересекающегося интервала ОПУС.",
        AppLanguage.KK: "Стандартты аралықпен қабаттасатын ОПУС аралығы жоқ.",
        AppLanguage.EN: "No OPUS interval overlaps the standard interval.",
    },
    "no_standard_depth_overlap": {
        AppLanguage.RU: "Для интервала ОПУС нет пересекающегося стандартного интервала.",
        AppLanguage.KK: "ОПУС аралығымен қабаттасатын стандартты аралық жоқ.",
        AppLanguage.EN: "No standard-method interval overlaps the OPUS interval.",
    },
    "multiple_opus_depth_overlaps": {
        AppLanguage.RU: "Один стандартный интервал пересекается с несколькими интервалами ОПУС; однозначная пара не установлена.",
        AppLanguage.KK: "Бір стандартты аралық бірнеше ОПУС аралығымен қабаттасады; бірмәнді жұп анықталмаған.",
        AppLanguage.EN: "One standard interval overlaps multiple OPUS intervals; there is no unique match.",
    },
    "multiple_standard_depth_overlaps": {
        AppLanguage.RU: "Один интервал ОПУС пересекается с несколькими стандартными интервалами; однозначная пара не установлена.",
        AppLanguage.KK: "Бір ОПУС аралығы бірнеше стандартты аралықпен қабаттасады; бірмәнді жұп анықталмаған.",
        AppLanguage.EN: "One OPUS interval overlaps multiple standard intervals; there is no unique match.",
    },
    "partial_depth_overlap": {
        AppLanguage.RU: "Общее пересечение покрывает менее половины хотя бы одного интервала; уверенное сопоставление границ невозможно.",
        AppLanguage.KK: "Ортақ бөлік кемінде бір аралықтың жартысынан азын қамтиды; шекараларды сенімді салыстыру мүмкін емес.",
        AppLanguage.EN: "The shared depth span covers less than half of at least one interval; interval correspondence is incomplete.",
    },
    "opus_no_valid_consensus": {
        AppLanguage.RU: "У ОПУС нет достаточных синхронных строк с однозначным итоговым классом; в том числе возможен класс 7.",
        AppLanguage.KK: "ОПУС бойынша бірмәнді қорытынды класы бар жарамды синхронды жолдар жеткіліксіз; 7-класс болуы мүмкін.",
        AppLanguage.EN: "OPUS lacks sufficient valid synchronous rows with a unique class; this includes class 7.",
    },
    "opus_indicator_evidence_missing": {
        AppLanguage.RU: "Нет полного набора результатов пяти индикаторов ОПУС для проверки классификации.",
        AppLanguage.KK: "Жіктеуді тексеруге ОПУС-тың бес көрсеткішінің толық нәтижелері жоқ.",
        AppLanguage.EN: "Results for all five OPUS indicators are not available for classification review.",
    },
    "opus_mixed_indicator_families": {
        AppLanguage.RU: "Голоса пяти индикаторов ОПУС разделены между нефтяными и газовыми группами; единый тип флюида не подтверждён.",
        AppLanguage.KK: "ОПУС-тың бес көрсеткішінің дауыстары мұнай және газ топтарына бөлінген; бірыңғай флюид түрі расталмаған.",
        AppLanguage.EN: "The five OPUS indicator votes span oil and gas families; a single fluid type is not established.",
    },
    "opus_class_four_unverified": {
        AppLanguage.RU: "Класс 4 ОПУС требует независимой геологической проверки; по нему нельзя утверждать наличие воды.",
        AppLanguage.KK: "ОПУС-тың 4-класы тәуелсіз геологиялық тексеруді қажет етеді; ол судың барын дәлелдемейді.",
        AppLanguage.EN: "OPUS class 4 requires independent geological validation and does not establish water presence.",
    },
    "opus_support_unavailable": {
        AppLanguage.RU: "Нет достоверного числового показателя поддержки класса ОПУС.",
        AppLanguage.KK: "ОПУС класын қолдаудың сенімді сандық мәні жоқ.",
        AppLanguage.EN: "No valid numeric support measure is available for the OPUS class.",
    },
    "standard_context_unavailable": {
        AppLanguage.RU: "Для стандартного интервала отсутствует оценка Pixler C1/C2 или корректное сопоставление wetness с фоном (robust-z).",
        AppLanguage.KK: "Стандартты аралықта Pixler C1/C2 бағасы немесе wetness көрсеткішін фонмен дұрыс салыстыру (robust-z) жоқ.",
        AppLanguage.EN: "The standard interval lacks Pixler C1/C2 or a valid wetness-to-background robust-z assessment.",
    },
    "fluid_phase_ambiguous": {
        AppLanguage.RU: "Одна из методик не определяет только газовую либо только жидкую фазу; смешанные признаки не являются расхождением.",
        AppLanguage.KK: "Әдістердің бірі тек газдық не тек сұйық фазаны анықтамайды; аралас белгілер айырмашылықты дәлелдемейді.",
        AppLanguage.EN: "At least one method has a mixed or indeterminate phase; this cannot establish a disagreement.",
    },
}

_UNKNOWN: dict[AppLanguage, str] = {
    AppLanguage.RU: "Причина требует проверки по исходным данным.",
    AppLanguage.KK: "Себепті бастапқы деректер бойынша тексеру қажет.",
    AppLanguage.EN: "The reason requires review against source data.",
}


def _number(value: float | None) -> str:
    if value is None or not isfinite(value):
        return "—"
    return f"{value:.4g}"


def _percent(value: float | None) -> str:
    if value is None or not isfinite(value):
        return "—"
    return f"{value * 100.0:.1f}%"


def _bounds(bounds: tuple[float, float] | None, unit: str) -> str:
    if bounds is None:
        return "—"
    return f"{bounds[0]:.2f}–{bounds[1]:.2f} {unit}".strip()


def method_comparison_html(
    items: tuple[MethodComparisonInterval, ...],
    language: AppLanguage = AppLanguage.RU,
    *,
    depth_unit: str = "m",
) -> str:
    """Render one optional analytical section, not a limitations/warning block."""

    def label(key: str) -> str:
        return escape(_HEADINGS[key][language])

    rows: list[str] = []
    for item in items:
        reason = _REASONS.get(item.reason_code, _UNKNOWN)
        metrics = (
            (label("overlap"), f"{_number(item.overlap_depth)} {escape(depth_unit)}"
             if item.standard_bounds is not None and item.opus_bounds is not None
             else "—"),
            (
                label("coverage"),
                f"{_percent(item.standard_overlap_fraction)} / "
                f"{_percent(item.opus_overlap_fraction)}",
            ),
            (label("wetness"), _number(item.standard_wetness_robust_z)),
            (label("pixler"), _number(item.standard_pixler_c1_c2)),
            (label("class"), str(item.opus_class_code) if item.opus_class_code is not None else "—"),
            (label("support"), _percent(item.opus_support_fraction)),
            (label("valid"), str(item.opus_valid_rows) if item.opus_valid_rows is not None else "—"),
        )
        evidence = "; ".join(f"{name}: {value}" for name, value in metrics)
        rows.append(
            f'<tr data-reason-version="{item.reason_schema_version}" '
            f'data-reason-code="{escape(item.reason_code, quote=True)}">'
            f"<td>{escape(_bounds(item.standard_bounds, depth_unit))}</td>"
            f"<td>{escape(_bounds(item.opus_bounds, depth_unit))}</td>"
            f"<td>{escape(_STATUSES[item.status][language])}</td>"
            f"<td>{escape(reason[language])}</td>"
            f"<td>{evidence}</td></tr>"
        )
    if not rows:
        content = f"<p>{label('none')}</p>"
    else:
        content = (
            "<table class='method-comparison-table'><thead><tr>"
            + "".join(
                f"<th>{label(key)}</th>"
                for key in ("standard", "opus", "status", "reason", "measurements")
            )
            + "</tr></thead><tbody>"
            + "".join(rows)
            + "</tbody></table>"
        )
    return (
        "<div class='method-comparison-analytics'>"
        f"<h2>{label('title')}</h2><p>{label('intro')}</p>"
        f"{content}</div>"
    )


__all__ = ["method_comparison_html"]
