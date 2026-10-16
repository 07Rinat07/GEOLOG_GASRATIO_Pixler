from __future__ import annotations

import pytest

from geoworkbench.services.hydrocarbon_interpretation_legacy import (
    _METHODS,
    build_hydrocarbon_interpretation_report,
    hydrocarbon_interpretation_html,
)
from geoworkbench.services.hydrocarbon_interpretation_report_locale import (
    localize_method_calculation,
    localize_method_name,
    localize_system_warning,
)
from geoworkbench.services.localization import AppLanguage
from test_interpretation_depth_interval import _session


@pytest.mark.parametrize("language", [AppLanguage.KK, AppLanguage.EN])
def test_built_in_methodology_is_localized_without_modifying_source_report(language):
    report = build_hydrocarbon_interpretation_report(_session())
    original_warnings = report.warnings
    original_methods = report.methods

    html = hydrocarbon_interpretation_html(report, language)

    assert "Автоматически отмечаются только кандидаты" not in html
    assert "Перед принятием интервалов проверьте" not in html
    assert "Нормализованный газ не рассчитан." not in html
    if language is AppLanguage.KK:
        assert "C1/C2, C1/C3, C1/ΣC4 and C1/ΣC5;" not in html
        assert "Pixler: көмірсутек қатынастары" in html
        assert "палетка бойынша алдын ала бағаланады" in html
    else:
        assert "Only prospective intervals based on relative gas anomalies" in html
    assert report.warnings == original_warnings
    assert report.methods == original_methods


@pytest.mark.parametrize("language", [AppLanguage.KK, AppLanguage.EN])
def test_all_standard_method_explanations_have_kazakh_presentations(language):
    for name, _curves, _source, calculation in _METHODS:
        rendered_name = localize_method_name(name, language)
        rendered_calculation = localize_method_calculation(calculation, language)
        if language is AppLanguage.KK:
            assert rendered_name != name
            assert rendered_calculation != calculation
            assert any(letter in rendered_name for letter in "әғқңөұүі")
        else:
            assert rendered_name == name
            assert rendered_calculation == calculation


@pytest.mark.parametrize("language", [AppLanguage.KK, AppLanguage.EN])
def test_normalized_gas_dynamic_diagnostics_preserve_curve_identifiers(language):
    warnings = (
        "Серверная/файловая кривая TG_NORM сохранена без перезаписи.",
        "Локальная кривая TG_NORM_CALC рассчитана программой и хранится отдельно.",
        "Не найдена локально рассчитанная кривая нормализованного газа с минимум 20 корректными отсчётами.",
        (
            "Сравнение серверного и локального нормализованного газа выполнено по "
            "собственному robust-фону каждой кривой: совпадающих интервалов 2, "
            "только серверных 1, только локальных 3. "
            "Каждый интервал отдельно сопоставлен с ЛБА."
        ),
        "TG_NORM (server): Газовая кривая не имеет достаточного разброса для поиска аномалий.",
    )
    localized = tuple(localize_system_warning(value, language) for value in warnings)
    assert all(after != before for after, before in zip(localized, warnings))
    assert "TG_NORM" in localized[0]
    assert "TG_NORM_CALC" in localized[1]
    assert "2" in localized[3] and "1" in localized[3] and "3" in localized[3]
    assert "TG_NORM (server):" in localized[4]


def test_operator_entered_warnings_are_not_guessed_or_mutated():
    comment = "Слой глины пиритизирован. Верификация по шламу."
    assert localize_system_warning(comment, AppLanguage.KK) == comment
    assert localize_system_warning(comment, AppLanguage.EN) == comment
