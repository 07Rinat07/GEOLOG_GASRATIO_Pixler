from __future__ import annotations

import pytest

from geoworkbench.printing.auto_pagination import (
    automatic_tablet_first_page_geometry,
    automatic_tablet_page_geometry,
    printable_tablet_body_height_mm,
)


def test_auto_interval_expands_wide_landscape_form_to_printable_height() -> None:
    geometry = automatic_tablet_page_geometry(
        source_width_px=2800,
        source_content_height_px=700,
        header_height_px=120,
        current_span=50.0,
        content_width_mm=277.0,
        content_height_mm=190.0,
    )

    assert geometry.target_content_height_px > 700
    assert geometry.units_per_page > 100.0
    assert geometry.page_aspect_ratio == pytest.approx(277.0 / 175.0)
    source_body_height = 700 - 120
    target_body_height = geometry.target_content_height_px - 120
    assert target_body_height / geometry.units_per_page == pytest.approx(
        source_body_height / 50.0
    )
    assert target_body_height * geometry.page_aspect_ratio == pytest.approx(2800, abs=1.0)


def test_auto_interval_keeps_tall_forms_at_the_current_density() -> None:
    geometry = automatic_tablet_page_geometry(
        source_width_px=900,
        source_content_height_px=1400,
        header_height_px=100,
        current_span=50.0,
        content_width_mm=277.0,
        content_height_mm=190.0,
    )

    assert geometry.target_content_height_px == 1400
    assert geometry.units_per_page == pytest.approx(50.0)


@pytest.mark.parametrize(
    "overrides",
    [
        {"source_width_px": 0},
        {"source_content_height_px": 0},
        {"header_height_px": 700},
        {"current_span": 0.0},
        {"content_width_mm": 0.0},
        {"content_height_mm": 0.0},
    ],
)
def test_auto_interval_rejects_invalid_geometry(overrides: dict[str, float | int]) -> None:
    values: dict[str, float | int] = {
        "source_width_px": 2800,
        "source_content_height_px": 700,
        "header_height_px": 120,
        "current_span": 50.0,
        "content_width_mm": 277.0,
        "content_height_mm": 190.0,
    }
    values.update(overrides)

    with pytest.raises(ValueError):
        automatic_tablet_page_geometry(**values)  # type: ignore[arg-type]


def test_first_page_reduces_interval_for_visible_column_header() -> None:
    geometry = automatic_tablet_first_page_geometry(
        canonical_content_height_px=1000,
        column_header_height_px=200,
        regular_units_per_page=100.0,
        regular_body_height_mm=175.0,
        first_body_height_mm=175.0,
    )

    assert geometry.target_content_height_px == 800
    assert geometry.units_per_page == pytest.approx(75.0)


def test_full_report_header_reduces_first_page_interval_further() -> None:
    geometry = automatic_tablet_first_page_geometry(
        canonical_content_height_px=1000,
        column_header_height_px=200,
        regular_units_per_page=100.0,
        regular_body_height_mm=175.0,
        first_body_height_mm=140.0,
    )

    assert geometry.target_content_height_px == 640
    assert geometry.units_per_page == pytest.approx(55.0)


def test_printable_body_height_accounts_for_selected_header_band() -> None:
    assert printable_tablet_body_height_mm(190.0) == pytest.approx(175.0)
    assert printable_tablet_body_height_mm(
        190.0,
        header_band_mm=32.0,
    ) == pytest.approx(150.0)
