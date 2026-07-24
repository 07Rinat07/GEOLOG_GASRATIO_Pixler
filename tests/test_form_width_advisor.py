from geoworkbench.printing.form_width_advisor import (
    FormWidthLevel,
    audit_form_width,
    mm_to_px,
    px_to_mm,
)


def test_width_conversion_round_trip_is_stable() -> None:
    width = mm_to_px(190.0)
    assert width == 718
    assert abs(px_to_mm(width) - 190.0) < 0.2


def test_portrait_form_is_detected() -> None:
    audit = audit_form_width((180, 180, 180))
    assert audit.level is FormWidthLevel.FITS_PORTRAIT
    assert audit.portrait_overflow_px == 0
    assert audit.portrait_pages_at_actual_size == 1


def test_landscape_recommendation_is_detected() -> None:
    audit = audit_form_width((260, 260, 260))
    assert audit.level is FormWidthLevel.FITS_LANDSCAPE
    assert audit.portrait_overflow_px > 0
    assert audit.landscape_overflow_px == 0


def test_wide_form_recommends_split_when_scale_is_too_small() -> None:
    audit = audit_form_width((260,) * 10)
    assert audit.level is FormWidthLevel.NEEDS_SPLIT
    assert audit.portrait_pages_at_actual_size >= 3
    assert audit.landscape_scale_percent < 70.0


def test_hidden_zero_width_columns_do_not_count() -> None:
    audit = audit_form_width((180, 0, 180))
    assert audit.visible_columns == 2
    assert audit.total_width_px == 362
