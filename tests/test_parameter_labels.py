from __future__ import annotations

from geoworkbench.services.localization import AppLanguage
from geoworkbench.services.parameter_labels import (
    localized_curve_name,
    localized_curve_reference,
)


def test_legacy_vendor_sensor_codes_are_shown_as_readable_names() -> None:
    assert localized_curve_name("S300", unit="атм") == "Давление на манифольде"
    assert localized_curve_name("S720", unit="м3") == "Суммарный объем в емкостях"
    assert localized_curve_name("S800", unit="°C") == "Температура на входе"
    assert localized_curve_name("S900", unit="°C") == "Температура раствора на выходе"
    assert localized_curve_name("S50", unit="мин-1") == "Число ходов 1 насоса"


def test_raw_mnemonic_saved_as_display_name_does_not_hide_catalog_label() -> None:
    assert (
        localized_curve_name(
            "S300",
            unit="атм",
            configured="S300",
            language=AppLanguage.RU,
        )
        == "Давление на манифольде"
    )


def test_explicit_user_caption_still_has_priority() -> None:
    assert (
        localized_curve_name(
            "S300",
            unit="атм",
            configured="Давление буровых насосов",
            language=AppLanguage.RU,
        )
        == "Давление буровых насосов"
    )


def test_explicit_gamma_description_overrides_reused_geoscape_gid() -> None:
    assert (
        localized_curve_name(
            "S810",
            description="гамма",
            unit="API",
            language=AppLanguage.RU,
        )
        == "Гамма-каротаж"
    )


def test_geoscape2_gid_810_is_available_when_source_has_no_description() -> None:
    assert localized_curve_name("S810", unit="°C") == "Температура в емкости 8"


def test_unresolved_vendor_channel_is_presented_without_duplicate_technical_text() -> None:
    assert (
        localized_curve_name("S811", description="Исходный канал S811")
        == "Неопределённый канал"
    )
    assert localized_curve_name("S811") == "Неопределённый канал"

def test_legacy_gas_vendor_codes_use_physical_parameter_names() -> None:
    assert localized_curve_name("S1601", unit="%") == "Содержание метана"
    assert localized_curve_name("S1602", unit="%") == "Этан"
    assert localized_curve_name("S1603", unit="%") == "Пропан"
    assert localized_curve_name("S1604", unit="%") == "Бутан"
    assert localized_curve_name("S1605", unit="%") == "Пентан"
    assert localized_curve_name("S1626", unit="%") == "Изобутан"
    assert localized_curve_name("S1627", unit="%") == "Изопентан"


def test_common_non_hydrocarbon_gases_have_physical_names_in_all_languages() -> None:
    expected = {
        "H2S": ("Сероводород", "Күкіртсутек", "Hydrogen sulfide"),
        "CO2": ("Диоксид углерода", "Көмірқышқыл газы", "Carbon dioxide"),
        "N2": ("Азот", "Азот", "Nitrogen"),
    }
    for mnemonic, (ru, kk, en) in expected.items():
        assert localized_curve_name(mnemonic, language=AppLanguage.RU) == ru
        assert localized_curve_name(mnemonic, language=AppLanguage.KK) == kk
        assert localized_curve_name(mnemonic, language=AppLanguage.EN) == en


def test_normalized_gas_calculation_curve_has_readable_report_name() -> None:
    assert (
        localized_curve_name("TG_NORM_CALC", language=AppLanguage.RU)
        == "Расчётный нормализованный общий газ"
    )
    assert (
        localized_curve_name("TG_NORM_CALC", language=AppLanguage.EN)
        == "Calculated Normalized Total Gas"
    )
    assert (
        localized_curve_name("TG_NORM_CALC", language=AppLanguage.KK)
        == "Есептелген нормаланған жалпы газ"
    )


def test_reference_normalized_methane_has_readable_report_name() -> None:
    assert (
        localized_curve_name("C1_NORM_REF", language=AppLanguage.RU)
        == "Нормализованный метан по опорной кривой"
    )
    assert (
        localized_curve_name("C1_NORM_REF", language=AppLanguage.EN)
        == "Reference-normalized Methane"
    )
    assert (
        localized_curve_name("C1_NORM_REF", language=AppLanguage.KK)
        == "Тірек қисығы бойынша нормаланған метан"
    )




def test_report_curve_reference_hides_vendor_mnemonics() -> None:
    assert localized_curve_reference("S224", language=AppLanguage.RU) == "D-exponent"
    assert (
        localized_curve_reference(
            "server: S1600 | local-calculation: TG_NORM_CALC",
            language=AppLanguage.RU,
        )
        == "Сервер/файл: Общий газ | Локальный расчёт: Расчётный нормализованный общий газ"
    )
    assert "S224" not in localized_curve_reference("S224", language=AppLanguage.EN)
    assert "S224" not in localized_curve_reference("S224", language=AppLanguage.KK)



def test_opus_report_parameters_have_readable_names_in_all_languages() -> None:
    assert localized_curve_name("OPUS_TG_PCT", language=AppLanguage.RU) == "Общий газ ОПУС"
    assert localized_curve_name("OPUS_TG_PCT", language=AppLanguage.KK) == "ОПУС жалпы газы"
    assert localized_curve_name("OPUS_TG_PCT", language=AppLanguage.EN) == "OPUS total gas"
    assert localized_curve_name("OPUS3", language=AppLanguage.RU) == "ОПУС-3"
    assert localized_curve_name("OPUS4", language=AppLanguage.EN) == "OPUS-4"
