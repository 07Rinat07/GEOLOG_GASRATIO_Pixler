from __future__ import annotations

import pytest

from geoworkbench.printing.print_layout import (
    PrintScaleMode,
    build_horizontal_continuations,
    resolve_media_dimensions,
    standard_media_size_mm,
)


def test_standard_a4_and_a3_dimensions_are_deterministic() -> None:
    assert standard_media_size_mm("a4") == (210.0, 297.0)
    assert standard_media_size_mm("a3") == (297.0, 420.0)


def test_landscape_media_swaps_physical_dimensions() -> None:
    media = resolve_media_dimensions(
        page_format="a4",
        orientation="landscape",
        custom_width_mm=210.0,
        custom_height_mm=297.0,
        margins_mm=(10.0, 10.0, 10.0, 10.0),
        content_width_px=1000,
        content_height_px=600,
        scale_mode=PrintScaleMode.FIT,
    )

    assert media.width_mm == 297.0
    assert media.height_mm == 210.0
    assert media.content_width_mm == 277.0
    assert media.content_height_mm == 190.0


def test_custom_media_preserves_requested_size_and_margins() -> None:
    media = resolve_media_dimensions(
        page_format="custom",
        orientation="portrait",
        custom_width_mm=320.0,
        custom_height_mm=900.0,
        margins_mm=(12.0, 15.0, 18.0, 20.0),
        content_width_px=900,
        content_height_px=600,
        scale_mode=PrintScaleMode.FIT,
    )

    assert (media.width_mm, media.height_mm) == (320.0, 900.0)
    assert (media.content_width_mm, media.content_height_mm) == (290.0, 865.0)


def test_roll_fit_length_uses_content_aspect_ratio() -> None:
    media = resolve_media_dimensions(
        page_format="roll",
        orientation="landscape",
        custom_width_mm=300.0,
        custom_height_mm=297.0,
        margins_mm=(10.0, 10.0, 10.0, 10.0),
        content_width_px=1000,
        content_height_px=2000,
        scale_mode=PrintScaleMode.FIT,
    )

    assert media.is_roll
    assert media.width_mm == 300.0
    assert media.height_mm == pytest.approx(580.0)
    assert media.content_height_mm == pytest.approx(560.0)


def test_roll_actual_size_uses_reference_96_dpi() -> None:
    media = resolve_media_dimensions(
        page_format="roll",
        orientation="portrait",
        custom_width_mm=300.0,
        custom_height_mm=297.0,
        margins_mm=(10.0, 10.0, 10.0, 10.0),
        content_width_px=1600,
        content_height_px=960,
        scale_mode=PrintScaleMode.ACTUAL_SIZE,
    )

    assert media.height_mm == pytest.approx(274.0)


def test_fit_mode_always_uses_one_horizontal_page() -> None:
    pages = build_horizontal_continuations(
        source_width_px=4000.0,
        available_width_mm=190.0,
        scale_mode=PrintScaleMode.FIT,
        overlap_mm=5.0,
    )

    assert len(pages) == 1
    assert pages[0].source_left_px == 0.0
    assert pages[0].source_right_px == 4000.0
    assert pages[0].rendered_width_mm == pytest.approx(190.0)


def test_actual_size_creates_stable_continuation_pages() -> None:
    pages = build_horizontal_continuations(
        source_width_px=2000.0,
        available_width_mm=190.0,
        scale_mode=PrintScaleMode.ACTUAL_SIZE,
        overlap_mm=5.0,
    )

    assert len(pages) == 3
    assert [page.index for page in pages] == [1, 2, 3]
    assert all(page.total == 3 for page in pages)
    assert pages[0].source_left_px == 0.0
    assert pages[-1].source_right_px == 2000.0
    overlap_px = 5.0 / 25.4 * 96.0
    assert pages[0].source_right_px - pages[1].source_left_px == pytest.approx(overlap_px)


def test_actual_size_rejects_overlap_equal_to_page_width() -> None:
    with pytest.raises(ValueError, match="smaller than printable width"):
        build_horizontal_continuations(
            source_width_px=2000.0,
            available_width_mm=20.0,
            scale_mode=PrintScaleMode.ACTUAL_SIZE,
            overlap_mm=20.0,
        )


def test_roll_length_is_capped_by_application_contract() -> None:
    media = resolve_media_dimensions(
        page_format="roll",
        orientation="portrait",
        custom_width_mm=300.0,
        custom_height_mm=297.0,
        margins_mm=(10.0, 10.0, 10.0, 10.0),
        content_width_px=100,
        content_height_px=100_000,
        scale_mode=PrintScaleMode.ACTUAL_SIZE,
    )

    assert media.height_mm == 5000.0
    assert media.content_height_mm == 4980.0
