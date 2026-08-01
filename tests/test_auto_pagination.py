from __future__ import annotations

import pytest

from geoworkbench.printing.auto_pagination import automatic_tablet_page_geometry


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
