from __future__ import annotations

from pathlib import Path

from geoworkbench.domain.models import IndexRole, IndexType
from geoworkbench.tablet.models import TrackDefinition, TrackKind
from geoworkbench.tablet.track_geometry import (
    DATETIME_AXIS_MIN_TRACK_WIDTH,
    RELATIVE_TIME_AXIS_MIN_TRACK_WIDTH,
    effective_track_width,
    horizontal_track_extent,
)


ROOT = Path(__file__).resolve().parents[1]


def test_datetime_axis_expansion_is_part_of_canvas_geometry() -> None:
    depth = TrackDefinition("time", "Time", TrackKind.DEPTH, width=48)
    curve = TrackDefinition("rop", "ROP", TrackKind.CURVE, width=280)

    time_width = effective_track_width(
        depth, axis_role=IndexRole.TIME, axis_type=IndexType.DATETIME
    )

    assert time_width == DATETIME_AXIS_MIN_TRACK_WIDTH
    assert effective_track_width(
        depth, axis_role=IndexRole.TIME, axis_type=IndexType.RELATIVE_TIME
    ) == RELATIVE_TIME_AXIS_MIN_TRACK_WIDTH
    assert effective_track_width(curve, axis_role=IndexRole.TIME) == 280
    assert horizontal_track_extent((time_width, curve.width), spacing=2) == 406


def test_gs2_refresh_uses_rendered_widths_for_tracks_and_group_headers() -> None:
    source = (
        ROOT / "src/geoworkbench/tablet/tablet_view.py"
    ).read_text(encoding="utf-8")

    assert "def _track_display_width(" in source
    assert "rendered.widget.display_width" in source
    assert "horizontal_track_extent(" in source
    group_method = source.split("    def _rebuild_group_headers", 1)[1].split(
        "    def _synchronize_track_header_bands", 1
    )[0]
    assert "self._track_display_width(track)" in group_method
    static_method = source.split("    def _apply_static_track_configuration", 1)[1].split(
        "    def _apply_curve_styles", 1
    )[0]
    assert "effective_track_width(" in static_method


def test_current_dataset_is_installed_in_one_tablet_render_pass() -> None:
    source = (
        ROOT / "src/geoworkbench/ui/main_window.py"
    ).read_text(encoding="utf-8")
    method = source.split("    def _show_current_dataset(self) -> None:", 1)[1].split(
        "    def show_las_editor", 1
    )[0]

    assert "self.tablet_view.set_dataset(dataset)" not in method
    assert "self.tablet_view.set_layout_and_dataset(layout, dataset)" in method
    assert method.count("refresh=False") >= 4
    assert method.index("refresh=False") < method.index(
        "self.tablet_view.set_layout_and_dataset(layout, dataset)"
    )


def test_default_tablet_command_uses_transactional_render() -> None:
    source = (
        ROOT / "src/geoworkbench/ui/main_window.py"
    ).read_text(encoding="utf-8")
    method = source.split("    def build_default_tablet(self) -> None:", 1)[1].split(
        "    def _set_tablet_edit_mode", 1
    )[0]

    assert "set_layout_and_dataset(layout, dataset)" in method
    assert "set_layout_model(layout)" not in method
    assert "set_dataset(dataset)" not in method
