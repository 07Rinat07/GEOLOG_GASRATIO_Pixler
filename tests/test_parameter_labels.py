from __future__ import annotations

from geoworkbench.services.localization import AppLanguage
from geoworkbench.services.parameter_labels import localized_curve_name


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
