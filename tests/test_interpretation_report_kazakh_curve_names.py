from __future__ import annotations

import numpy as np
import pytest

from geoworkbench.domain.models import CurveData, CurveMetadata
from geoworkbench.printing.hydrocarbon_interpretation_curve_labels import (
    curve_display_name,
)
from geoworkbench.services.localization import AppLanguage
from geoworkbench.services.parameter_labels import (
    localized_curve_name,
    localized_curve_reference,
)


@pytest.mark.parametrize(
    ("mnemonic", "kazakh_name"),
    (
        ("NORMALIZED_TOTAL_GAS", "Нормаланған жалпы газ"),
        ("TOTAL_GAS_NORM", "Нормаланған жалпы газ"),
        ("NORM_TG", "Нормаланған жалпы газ"),
        ("TGNORM", "Нормаланған жалпы газ"),
        ("OPUS_GM_1", "ОПУС Газомер — 1-көрсеткіш"),
        ("OPUS_GM_5", "ОПУС Газомер — 5-көрсеткіш"),
        ("OPUS_P1", "ОПУС үшін C1 компонентінің үлесі"),
        ("OPUS_P5", "ОПУС үшін C5 компонентінің үлесі"),
    ),
)
def test_kazakh_report_has_real_names_for_known_gas_and_opus_codes(
    mnemonic, kazakh_name,
):
    assert localized_curve_reference(mnemonic, language=AppLanguage.KK) == kazakh_name
    assert localized_curve_name(mnemonic, language=AppLanguage.KK) == kazakh_name


@pytest.mark.parametrize("language", list(AppLanguage))
def test_report_curve_presentation_preserves_exact_source_code(language):
    curve = CurveData(
        CurveMetadata(
            "sensor-opus-gm-2", "OPUS_GM_2", "OPUS_GM_2", "ratio",
            "Показатель ОПУС-2", "well-data",
        ),
        np.asarray([1.0, 2.0], dtype=np.float64),
    )
    original = curve.metadata.original_mnemonic
    label = curve_display_name(curve, language)
    assert label != "Показатель ОПУС-2"
    assert label != original
    assert "2" in label
    assert curve.metadata.original_mnemonic == original


def test_kazakh_authored_description_does_not_collapse_to_a_mnemonic():
    description = "Қазақша арнайы сипаттама"
    assert (
        localized_curve_name(
            "UNKNOWN_AZ_CHANNEL", description=description, language=AppLanguage.KK,
        )
        == description
    )


@pytest.mark.parametrize("language", [AppLanguage.KK, AppLanguage.EN])
def test_russian_vendor_description_is_not_leaked_into_localized_chart(language):
    source_description = "Неизвестная диагностическая кривая прибора"
    curve = CurveData(
        CurveMetadata(
            "unmapped", "UNKNOWN_VENDOR_900", "UNKNOWN_VENDOR_900", "unit",
            source_description, "well-data",
        ),
        np.asarray([1.0, 2.0], dtype=np.float64),
    )
    assert source_description not in curve_display_name(curve, language)
    # An unknown source code is kept rather than a made-up physical parameter.
    assert "UNKNOWN" in curve_display_name(curve, language)
    assert curve.metadata.description == source_description


def test_kazakh_custom_description_is_visible_in_chart():
    curve = CurveData(
        CurveMetadata(
            "custom", "CUSTOM_CHANNEL", "CUSTOM_CHANNEL", "unit",
            "Қазақша арнайы сипаттама", "well-data",
        ),
        np.asarray([1.0, 2.0], dtype=np.float64),
    )
    assert curve_display_name(curve, AppLanguage.KK) == "Қазақша арнайы сипаттама"
