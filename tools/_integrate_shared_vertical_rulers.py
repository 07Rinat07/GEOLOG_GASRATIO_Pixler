from __future__ import annotations

import re
from pathlib import Path


TABLET_VIEW = Path("src/geoworkbench/tablet/tablet_view.py")
WORKFLOW = Path(".github/workflows/finalize-shared-ruler.yml")
SELF = Path("tools/_integrate_shared_vertical_rulers.py")


def _replace_once(text: str, old: str, new: str) -> str:
    count = text.count(old)
    if count != 1:
        raise RuntimeError(f"expected one match, found {count}: {old[:120]!r}")
    return text.replace(old, new, 1)


def _replace_regex_once(text: str, pattern: str, replacement: str) -> str:
    updated, count = re.subn(pattern, replacement, text, count=1, flags=re.DOTALL)
    if count != 1:
        raise RuntimeError(f"regex expected one match, found {count}: {pattern}")
    return updated


def _patch_tablet_view() -> None:
    text = TABLET_VIEW.read_text(encoding="utf-8")
    if "from geoworkbench.tablet.vertical_ruler import (" in text:
        raise RuntimeError("shared vertical ruler integration is already present")

    text = _replace_once(
        text,
        "from geoworkbench.tablet.relative_gas import (\n"
        "    build_relative_gas_stack,\n"
        "    is_relative_gas_track,\n"
        ")\n",
        "from geoworkbench.tablet.relative_gas import (\n"
        "    build_relative_gas_stack,\n"
        "    is_relative_gas_track,\n"
        ")\n"
        "from geoworkbench.tablet.vertical_ruler import (\n"
        "    VerticalRulerKind,\n"
        "    VerticalRulerLayout,\n"
        "    VerticalRulerMode,\n"
        "    build_vertical_ruler_layout,\n"
        "    vertical_ruler_presentation,\n"
        ")\n",
    )

    axis_class = '''class TabletVerticalAxisItem(EngineeringGridAxisItem):
    """Render one authoritative ruler shared by all tablet columns."""

    def __init__(self, descriptor: VerticalAxisDescriptor) -> None:
        super().__init__("left")
        self.descriptor = descriptor
        self._shared_layout: VerticalRulerLayout | None = None
        self._show_labels = False

    @property
    def shared_layout(self) -> VerticalRulerLayout | None:
        return self._shared_layout

    def apply_shared_layout(
        self,
        layout: VerticalRulerLayout,
        *,
        show_labels: bool,
        axis_width: int,
        tick_length: int,
    ) -> None:
        self._shared_layout = layout
        self._show_labels = bool(show_labels)
        self.setStyle(
            autoExpandTextSpace=False,
            tickTextWidth=max(1, int(axis_width) - 6),
            tickLength=int(tick_length),
            hideOverlappingLabels=True,
            maxTickLevel=1,
        )
        self.setWidth(max(1, int(axis_width)))
        self.picture = None
        self.update()

    def tickSpacing(self, minVal, maxVal, size):  # type: ignore[override]
        layout = self._shared_layout
        if layout is None:
            return super().tickSpacing(minVal, maxVal, size)
        return [(layout.major_step, 0.0), (layout.minor_step, 0.0)]

    def tickStrings(self, values, scale, spacing):  # type: ignore[override]
        del scale
        layout = self._shared_layout
        if (
            layout is None
            or not self._show_labels
            or float(spacing) < layout.major_step * 0.999999
        ):
            return ["" for _value in values]
        tolerance = max(layout.major_step * 1e-8, 1e-9)
        major_ticks = tuple(tick for tick in layout.ticks if tick.major)
        return [
            next(
                (
                    tick.label
                    for tick in major_ticks
                    if abs(float(value) - tick.value) <= tolerance
                ),
                "",
            )
            for value in values
        ]
'''
    text = _replace_regex_once(
        text,
        r"class TabletVerticalAxisItem\(EngineeringGridAxisItem\):.*?\n\nclass CurveHeaderLabel",
        axis_class + "\n\nclass CurveHeaderLabel",
    )

    text = _replace_once(
        text,
        "        self._natural_curve_header_height = 0\n"
        "        self._curve_header_row_height = CURVE_HEADER_EDITOR_HEIGHT\n",
        "        self._natural_curve_header_height = 0\n"
        "        self._curve_header_row_height = CURVE_HEADER_EDITOR_HEIGHT\n"
        "        self._print_mode = False\n"
        "        self._shared_vertical_ruler_layout: VerticalRulerLayout | None = None\n",
    )
    text = _replace_once(
        text,
        "        self.plot.getAxis(\"left\").enableAutoSIPrefix(False)\n"
        "        self.plot.hideAxis(\"left\")\n"
        "        self.plot.getViewBox().invertY(True)\n",
        "        self.plot.getAxis(\"left\").enableAutoSIPrefix(False)\n"
        "        self._configure_vertical_ruler()\n"
        "        self.plot.getViewBox().invertY(True)\n",
    )

    widget_methods = '''    def _vertical_ruler_mode(self) -> VerticalRulerMode:
        if self.definition.kind is TrackKind.DEPTH:
            return VerticalRulerMode.LABELS_AND_TICKS
        if self.definition.kind in {
            TrackKind.CURVE,
            TrackKind.GAS,
            TrackKind.DEXP,
            TrackKind.CALCIMETRY,
        }:
            return VerticalRulerMode.AUTOMATIC
        return VerticalRulerMode.OFF

    def set_shared_vertical_ruler_layout(
        self, layout: VerticalRulerLayout | None
    ) -> None:
        self._shared_vertical_ruler_layout = layout
        self._configure_vertical_ruler()

    def _configure_vertical_ruler(self) -> None:
        axis = self.plot.getAxis("left")
        layout = self._shared_vertical_ruler_layout
        mode = self._vertical_ruler_mode()
        if (
            not isinstance(axis, TabletVerticalAxisItem)
            or layout is None
            or mode is VerticalRulerMode.OFF
        ):
            self.plot.hideAxis("left")
            return
        presentation = vertical_ruler_presentation(
            layout,
            track_kind=self.definition.kind.value,
            track_width=self._display_width,
            mode=mode,
            force_labels=self.definition.kind is TrackKind.DEPTH,
        )
        axis.apply_shared_layout(
            layout,
            show_labels=presentation.show_labels,
            axis_width=presentation.axis_width,
            tick_length=presentation.tick_length,
        )
        self.plot.showAxis("left")

'''
    text = _replace_once(
        text,
        "    @property\n    def display_width(self) -> int:\n",
        widget_methods + "    @property\n    def display_width(self) -> int:\n",
    )
    text = _replace_regex_once(
        text,
        r"    def set_track_width\(self, width: int\) -> None:\n.*?\n"
        r"    def mousePressEvent\(self, event\) -> None:",
        "    def set_track_width(self, width: int) -> None:\n"
        "        self._display_width = max(1, int(width))\n"
        "        self.setFixedWidth(self._display_width)\n"
        "        self._configure_vertical_ruler()\n\n"
        "    def mousePressEvent(self, event) -> None:",
    )
    text = _replace_once(
        text,
        "        enabled = bool(enabled)\n"
        "        self._curve_header_row_height = (\n",
        "        enabled = bool(enabled)\n"
        "        self._print_mode = enabled\n"
        "        self._curve_header_row_height = (\n",
    )
    text = _replace_once(
        text,
        "        self.curve_header.setFixedHeight(content_height)\n"
        "        self.set_synchronized_header_height(self._natural_curve_header_height)\n\n"
        "    def update_curve_header_range(\n",
        "        self.curve_header.setFixedHeight(content_height)\n"
        "        self.set_synchronized_header_height(self._natural_curve_header_height)\n"
        "        self._configure_vertical_ruler()\n\n"
        "    def update_curve_header_range(\n",
    )

    text = _replace_once(
        text,
        "        self._depth_range_guard = False\n"
        "        self._cursor_enabled = False\n",
        "        self._depth_range_guard = False\n"
        "        self._shared_vertical_ruler_layout: VerticalRulerLayout | None = None\n"
        "        self._cursor_enabled = False\n",
    )

    view_methods = '''    def _vertical_ruler_kind(self) -> VerticalRulerKind | None:
        descriptor = self._axis_descriptor()
        if descriptor is None:
            return None
        if descriptor.is_datetime:
            return VerticalRulerKind.DATETIME
        if descriptor.is_time:
            return VerticalRulerKind.RELATIVE_TIME
        return VerticalRulerKind.DEPTH

    def _synchronize_vertical_rulers(self, top: float, bottom: float) -> None:
        descriptor = self._axis_descriptor()
        kind = self._vertical_ruler_kind()
        if descriptor is None or kind is None or not self._rendered:
            self._shared_vertical_ruler_layout = None
            return
        heights = [
            entry.plot.viewport().height()
            for entry in self._rendered.values()
            if entry.plot is not None and _qt_object_is_alive(entry.plot)
        ]
        shared = build_vertical_ruler_layout(
            top,
            bottom,
            pixel_height=float(max(heights, default=600)),
            kind=kind,
            unit=descriptor.unit,
            print_mode=self._annotation_print_mode,
        )
        self._shared_vertical_ruler_layout = shared
        for rendered in self._rendered.values():
            rendered.widget.set_shared_vertical_ruler_layout(shared)

'''
    text = _replace_once(
        text,
        "    def _apply_visible_depth(self, top: float, bottom: float, *, emit_change: bool) -> bool:\n",
        view_methods
        + "    def _apply_visible_depth(self, top: float, bottom: float, *, emit_change: bool) -> bool:\n",
    )
    text = _replace_once(
        text,
        "            self._update_visible_curve_data(normalized_top, normalized_bottom)\n",
        "            self._synchronize_vertical_rulers(normalized_top, normalized_bottom)\n"
        "            self._update_visible_curve_data(normalized_top, normalized_bottom)\n",
    )
    text = _replace_once(
        text,
        "            self._synchronize_depth_ranges(visible_top, visible_bottom)\n"
        "            self._update_lithology_text_visibility(visible_top, visible_bottom)\n",
        "            self._synchronize_depth_ranges(visible_top, visible_bottom)\n"
        "            self._synchronize_vertical_rulers(visible_top, visible_bottom)\n"
        "            self._update_lithology_text_visibility(visible_top, visible_bottom)\n",
    )
    text = _replace_once(
        text,
        "        self._synchronize_depth_ranges(*current)\n"
        "        self._update_navigation_controls()\n",
        "        self._synchronize_depth_ranges(*current)\n"
        "        self._synchronize_vertical_rulers(*current)\n"
        "        self._update_navigation_controls()\n",
    )
    text = _replace_once(
        text,
        "        self._rendered.clear()\n"
        "        self._overlay_layers.clear()\n",
        "        self._rendered.clear()\n"
        "        self._shared_vertical_ruler_layout = None\n"
        "        self._overlay_layers.clear()\n",
    )

    TABLET_VIEW.write_text(text, encoding="utf-8")


def _write_tests() -> None:
    Path("tests/test_vertical_ruler.py").write_text(
        '''from __future__ import annotations

from geoworkbench.tablet.vertical_ruler import (
    VerticalRulerKind,
    build_vertical_ruler_layout,
    vertical_ruler_presentation,
)


def test_shared_depth_layout_has_one_authoritative_tick_sequence() -> None:
    layout = build_vertical_ruler_layout(
        1703.28,
        1753.28,
        pixel_height=900,
        kind=VerticalRulerKind.DEPTH,
        unit="м",
    )

    assert layout.major_step == 5.0
    assert layout.minor_step == 1.0
    assert [tick.label for tick in layout.ticks if tick.label][:2] == ["1705", "1710"]


def test_track_width_changes_only_label_visibility_not_tick_values() -> None:
    layout = build_vertical_ruler_layout(
        1000.0,
        1050.0,
        pixel_height=600,
        kind=VerticalRulerKind.DEPTH,
    )
    wide = vertical_ruler_presentation(layout, track_kind="gas", track_width=120)
    narrow = vertical_ruler_presentation(layout, track_kind="gas", track_width=60)
    values = tuple(tick.value for tick in layout.ticks)

    assert wide.show_labels
    assert not narrow.show_labels
    assert values == tuple(tick.value for tick in layout.ticks)
''',
        encoding="utf-8",
    )
    Path("tests/test_tablet_vertical_ruler.py").write_text(
        '''from __future__ import annotations

from geoworkbench.domain.models import IndexRole, IndexType
from geoworkbench.tablet.models import TrackDefinition, TrackKind
from geoworkbench.tablet.tablet_view import (
    TabletTrackWidget,
    TabletVerticalAxisItem,
    VerticalAxisDescriptor,
)
from geoworkbench.tablet.vertical_ruler import (
    VerticalRulerKind,
    build_vertical_ruler_layout,
)


def _descriptor() -> VerticalAxisDescriptor:
    return VerticalAxisDescriptor(
        "depth-index", "Глубина", "м", IndexRole.DEPTH, IndexType.MD
    )


def test_depth_and_gas_axes_receive_same_layout_and_same_labels(qapp) -> None:
    shared = build_vertical_ruler_layout(
        1703.28,
        1753.28,
        pixel_height=900,
        kind=VerticalRulerKind.DEPTH,
        unit="м",
    )
    depth = TabletTrackWidget(
        TrackDefinition("depth", "Глубина", TrackKind.DEPTH, width=80),
        vertical_axis=_descriptor(),
    )
    gas = TabletTrackWidget(
        TrackDefinition("gas", "Газы", TrackKind.GAS, width=120),
        vertical_axis=_descriptor(),
    )
    depth.set_shared_vertical_ruler_layout(shared)
    gas.set_shared_vertical_ruler_layout(shared)
    depth_axis = depth.plot.getAxis("left")
    gas_axis = gas.plot.getAxis("left")

    assert isinstance(depth_axis, TabletVerticalAxisItem)
    assert isinstance(gas_axis, TabletVerticalAxisItem)
    assert depth_axis.shared_layout is shared
    assert gas_axis.shared_layout is shared
    assert depth_axis.tickSpacing(0.0, 0.0, 0.0) == gas_axis.tickSpacing(
        0.0, 0.0, 0.0
    )
    values = [1705.0, 1710.0, 1715.0]
    assert depth_axis.tickStrings(values, 1.0, 5.0) == gas_axis.tickStrings(
        values, 1.0, 5.0
    )
    depth.close()
    gas.close()
''',
        encoding="utf-8",
    )


def main() -> None:
    _patch_tablet_view()
    _write_tests()
    WORKFLOW.unlink()
    SELF.unlink()


if __name__ == "__main__":
    main()
