from __future__ import annotations

from pathlib import Path
import re


TABLET_VIEW = Path("src/geoworkbench/tablet/tablet_view.py")
TABLET_TEST = Path("tests/test_tablet_view.py")


def replace_once(path: Path, old: str, new: str) -> None:
    text = path.read_text(encoding="utf-8")
    count = text.count(old)
    if count != 1:
        raise RuntimeError(
            f"{path}: expected one replacement, found {count}: {old[:120]!r}"
        )
    path.write_text(text.replace(old, new, 1), encoding="utf-8")


def replace_regex_once(path: Path, pattern: str, replacement: str) -> None:
    text = path.read_text(encoding="utf-8")
    updated, count = re.subn(pattern, replacement, text, count=1, flags=re.DOTALL)
    if count != 1:
        raise RuntimeError(f"{path}: expected one regex replacement, found {count}")
    path.write_text(updated, encoding="utf-8")


def patch_tablet_view() -> None:
    replace_once(
        TABLET_VIEW,
        "from geoworkbench.tablet.grid_renderer import (\n"
        "    EngineeringGridAxisItem,\n"
        "    GridSettings,\n"
        "    TabletGridRenderer,\n"
        ")\n",
        "from geoworkbench.tablet.grid_renderer import (\n"
        "    EngineeringGridAxisItem,\n"
        "    GridSettings,\n"
        "    TabletGridRenderer,\n"
        ")\n"
        "from geoworkbench.tablet.vertical_ruler import (\n"
        "    VerticalRulerKind,\n"
        "    VerticalRulerLayout,\n"
        "    VerticalRulerMode,\n"
        "    VerticalRulerTrackSettings,\n"
        "    build_vertical_ruler_layout,\n"
        "    vertical_ruler_presentation,\n"
        "    visible_vertical_ruler_ticks,\n"
        ")\n",
    )

    axis_class = '''class TabletVerticalAxisItem(EngineeringGridAxisItem):
    """PyQtGraph adapter for one tablet-wide vertical-ruler layout.

    Tick values are never calculated by an individual axis. ``TabletView``
    resolves one immutable layout for the current depth/time window and every
    track receives either that full sequence or a configured subset of it.
    """

    def __init__(self, descriptor: VerticalAxisDescriptor) -> None:
        super().__init__("left")
        self.descriptor = descriptor
        self._shared_layout: VerticalRulerLayout | None = None

    @property
    def shared_layout(self) -> VerticalRulerLayout | None:
        return self._shared_layout

    def clear_shared_layout(self) -> None:
        self._shared_layout = None
        self.setTicks(None)

    def apply_shared_layout(
        self,
        layout: VerticalRulerLayout,
        settings: VerticalRulerTrackSettings,
        *,
        show_labels: bool,
        axis_width: int,
        tick_length: int,
    ) -> None:
        self._shared_layout = layout
        visible_ticks = visible_vertical_ruler_ticks(layout, settings)
        major_ticks = [
            (tick.value, tick.label if show_labels else "")
            for tick in visible_ticks
            if tick.major
        ]
        minor_ticks = [
            (tick.value, "")
            for tick in visible_ticks
            if not tick.major
        ]
        levels: list[list[tuple[float, str]]] = [major_ticks]
        if minor_ticks:
            levels.append(minor_ticks)
        self.setTicks(levels)
        self.setStyle(
            autoExpandTextSpace=False,
            tickTextWidth=max(1, int(axis_width) - 6),
            tickLength=int(tick_length),
            hideOverlappingLabels=True,
            maxTickLevel=1,
        )
        self.setWidth(max(1, int(axis_width)))

'''
    replace_regex_once(
        TABLET_VIEW,
        r"class TabletVerticalAxisItem\(EngineeringGridAxisItem\):.*?\n\nclass CurveHeaderLabel",
        axis_class + "class CurveHeaderLabel",
    )

    replace_once(
        TABLET_VIEW,
        "        self._natural_curve_header_height = 0\n"
        "        self._curve_header_row_height = CURVE_HEADER_EDITOR_HEIGHT\n",
        "        self._natural_curve_header_height = 0\n"
        "        self._curve_header_row_height = CURVE_HEADER_EDITOR_HEIGHT\n"
        "        self._shared_vertical_ruler_layout: VerticalRulerLayout | None = None\n",
    )

    widget_methods = '''    @staticmethod
    def _supports_inner_vertical_ruler(kind: TrackKind) -> bool:
        return kind in {
            TrackKind.CURVE,
            TrackKind.GAS,
            TrackKind.DEXP,
            TrackKind.CALCIMETRY,
        }

    def _vertical_ruler_settings(self) -> VerticalRulerTrackSettings:
        if self.definition.kind is TrackKind.DEPTH:
            return VerticalRulerTrackSettings(
                mode=VerticalRulerMode.LABELS_AND_TICKS
            )
        if self._supports_inner_vertical_ruler(self.definition.kind):
            return self.definition.vertical_ruler
        return VerticalRulerTrackSettings(mode=VerticalRulerMode.OFF)

    def set_shared_vertical_ruler_layout(
        self, layout: VerticalRulerLayout | None
    ) -> None:
        self._shared_vertical_ruler_layout = layout
        self._configure_vertical_ruler()

    def _configure_vertical_ruler(self) -> None:
        axis = self.plot.getAxis("left")
        if not isinstance(axis, TabletVerticalAxisItem):
            self.plot.hideAxis("left")
            return
        layout = self._shared_vertical_ruler_layout
        if layout is None:
            axis.clear_shared_layout()
            self.plot.hideAxis("left")
            return
        settings = self._vertical_ruler_settings()
        presentation = vertical_ruler_presentation(
            layout,
            track_kind=self.definition.kind.value,
            track_width=self._display_width,
            settings=settings,
            force_labels=self.definition.kind is TrackKind.DEPTH,
        )
        if not presentation.show_axis:
            axis.clear_shared_layout()
            self.plot.hideAxis("left")
            return
        axis.apply_shared_layout(
            layout,
            settings,
            show_labels=presentation.show_labels,
            axis_width=presentation.axis_width,
            tick_length=presentation.tick_length,
        )
        self.plot.showAxis("left")

'''
    replace_once(
        TABLET_VIEW,
        "    @property\n"
        "    def display_width(self) -> int:\n",
        widget_methods
        + "    @property\n"
        "    def display_width(self) -> int:\n",
    )

    replace_once(
        TABLET_VIEW,
        "    def set_track_width(self, width: int) -> None:\n"
        "        self._display_width = max(1, int(width))\n"
        "        self.setFixedWidth(self._display_width)\n"
        "        if self.definition.kind is TrackKind.DEPTH:\n"
        "            axis = self.plot.getAxis(\"left\")\n"
        "            axis_width = max(36, min(int(width) - 8, 92))\n"
        "            axis.setStyle(\n"
        "                autoExpandTextSpace=False,\n"
        "                tickTextWidth=max(30, min(int(width) - 12, 88)),\n"
        "                tickLength=-6,\n"
        "                hideOverlappingLabels=True,\n"
        "            )\n"
        "            axis.setWidth(axis_width)\n",
        "    def set_track_width(self, width: int) -> None:\n"
        "        self._display_width = max(1, int(width))\n"
        "        self.setFixedWidth(self._display_width)\n"
        "        self._configure_vertical_ruler()\n",
    )

    replace_once(
        TABLET_VIEW,
        "        self._sync_guard = False\n"
        "        self._depth_range_guard = False\n"
        "        self._cursor_enabled = False\n",
        "        self._sync_guard = False\n"
        "        self._depth_range_guard = False\n"
        "        self._shared_vertical_ruler_layout: VerticalRulerLayout | None = None\n"
        "        self._cursor_enabled = False\n",
    )

    view_methods = '''    @property
    def shared_vertical_ruler_layout(self) -> VerticalRulerLayout | None:
        return self._shared_vertical_ruler_layout

    def _vertical_ruler_kind(self) -> VerticalRulerKind | None:
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
        live_entries = tuple(
            entry
            for entry in self._rendered.values()
            if entry.plot is not None and _qt_object_is_alive(entry.plot)
        )
        if descriptor is None or kind is None or not live_entries:
            self._shared_vertical_ruler_layout = None
            for rendered in self._rendered.values():
                rendered.widget.set_shared_vertical_ruler_layout(None)
            return
        viewport_height = max(
            (
                entry.plot.viewport().height()
                for entry in live_entries
                if entry.plot is not None
            ),
            default=max(240, self.height()),
        )
        shared = build_vertical_ruler_layout(
            top,
            bottom,
            pixel_height=float(max(1, viewport_height)),
            kind=kind,
            unit=descriptor.unit,
            print_mode=self._annotation_print_mode,
            settings=self._layout_model.vertical_ruler_scale,
        )
        self._shared_vertical_ruler_layout = shared
        for rendered in live_entries:
            rendered.widget.set_shared_vertical_ruler_layout(shared)

'''
    replace_once(
        TABLET_VIEW,
        "    def _apply_visible_depth(self, top: float, bottom: float, *, emit_change: bool) -> bool:\n",
        view_methods
        + "    def _apply_visible_depth(self, top: float, bottom: float, *, emit_change: bool) -> bool:\n",
    )

    replace_once(
        TABLET_VIEW,
        "            self._update_visible_curve_data(normalized_top, normalized_bottom)\n",
        "            self._synchronize_vertical_rulers(normalized_top, normalized_bottom)\n"
        "            self._update_visible_curve_data(normalized_top, normalized_bottom)\n",
    )

    replace_once(
        TABLET_VIEW,
        "        self._rendered.clear()\n"
        "        self._overlay_layers.clear()\n",
        "        self._rendered.clear()\n"
        "        self._shared_vertical_ruler_layout = None\n"
        "        self._overlay_layers.clear()\n",
    )

    replace_once(
        TABLET_VIEW,
        "            self._synchronize_depth_ranges(visible_top, visible_bottom)\n"
        "            self._update_lithology_text_visibility(visible_top, visible_bottom)\n",
        "            self._synchronize_depth_ranges(visible_top, visible_bottom)\n"
        "            self._synchronize_vertical_rulers(visible_top, visible_bottom)\n"
        "            self._update_lithology_text_visibility(visible_top, visible_bottom)\n",
    )

    resize_anchor = (
        "        self._synchronize_depth_ranges(*current)\n"
        "        self._update_navigation_controls()\n"
    )
    text = TABLET_VIEW.read_text(encoding="utf-8")
    if resize_anchor in text:
        replace_once(
            TABLET_VIEW,
            resize_anchor,
            "        self._synchronize_depth_ranges(*current)\n"
            "        self._synchronize_vertical_rulers(*current)\n"
            "        self._update_navigation_controls()\n",
        )


def patch_existing_test() -> None:
    replacement = '''def test_tablet_uses_one_shared_unscaled_depth_axis_in_graphical_tracks(qapp) -> None:
    dataset = Dataset(
        "dataset-1",
        "Dataset",
        DatasetKind.GTI,
        DepthDomain.MD,
        np.array([950.0, 1100.0, 1250.0]),
    )
    view = TabletView()
    view.set_layout_model(
        TabletLayout(
            [
                TrackDefinition("depth", "Depth", TrackKind.DEPTH, width=120),
                TrackDefinition("curve", "Curve", TrackKind.CURVE, width=220),
            ]
        )
    )

    view.set_dataset(dataset)

    shared = view.shared_vertical_ruler_layout
    depth_axis = view._rendered["depth"].plot.getAxis("left")
    curve_axis = view._rendered["curve"].plot.getAxis("left")
    assert shared is not None
    assert isinstance(depth_axis, TabletVerticalAxisItem)
    assert isinstance(curve_axis, TabletVerticalAxisItem)
    assert depth_axis.isVisible()
    assert curve_axis.isVisible()
    assert depth_axis.autoSIPrefix is False
    assert curve_axis.autoSIPrefix is False
    assert depth_axis.shared_layout is shared
    assert curve_axis.shared_layout is shared
    assert view._rendered["depth"].plot.toolTip().startswith("Колесо — прокрутка")
    view.close()
'''
    replace_regex_once(
        TABLET_TEST,
        r"def test_tablet_uses_single_unscaled_depth_axis\(qapp\) -> None:.*?\n\n(?=def test_tablet_cursor_line)",
        replacement + "\n",
    )
    replace_once(
        TABLET_TEST,
        "    TabletTrackWidget,\n"
        "    TabletView,\n",
        "    TabletTrackWidget,\n"
        "    TabletVerticalAxisItem,\n"
        "    TabletView,\n",
    )


def create_tests() -> None:
    Path("tests/test_tablet_shared_vertical_ruler.py").write_text(
        '''from __future__ import annotations

import numpy as np

from geoworkbench.domain.models import (
    CurveData,
    CurveMetadata,
    Dataset,
    DatasetKind,
    DepthDomain,
)
from geoworkbench.tablet.models import TabletLayout, TrackDefinition, TrackKind
from geoworkbench.tablet.tablet_view import TabletVerticalAxisItem, TabletView
from geoworkbench.tablet.vertical_ruler import (
    VerticalRulerMode,
    VerticalRulerScaleSettings,
    VerticalRulerTrackSettings,
)


def _dataset() -> Dataset:
    depth = np.arange(1700.0, 1751.0, dtype=np.float64)
    dataset = Dataset(
        "shared-ruler-dataset",
        "Shared ruler",
        DatasetKind.GTI,
        DepthDomain.MD,
        depth,
    )
    curve = CurveData(
        CurveMetadata(
            "curve-c1",
            "C1",
            "C1",
            "%",
            None,
            dataset.dataset_id,
        ),
        np.linspace(1.0, 2.0, depth.size),
    )
    dataset.curves[curve.metadata.curve_id] = curve
    return dataset


def _axis_values(axis: TabletVerticalAxisItem) -> tuple[float, ...]:
    layout = axis.shared_layout
    assert layout is not None
    levels = axis.tickValues(layout.minimum, layout.maximum, 600.0)
    return tuple(
        float(value)
        for _spacing, ticks in levels
        for value, _label in ticks
    )


def _axis_labels(axis: TabletVerticalAxisItem) -> tuple[str, ...]:
    layout = axis.shared_layout
    assert layout is not None
    levels = axis.tickValues(layout.minimum, layout.maximum, 600.0)
    return tuple(
        str(label)
        for _spacing, ticks in levels
        for _value, label in ticks
        if str(label)
    )


def test_depth_and_graphical_tracks_share_one_layout_object_and_tick_values(qapp) -> None:
    view = TabletView()
    view.set_layout_model(
        TabletLayout(
            tracks=[
                TrackDefinition("depth", "Depth", TrackKind.DEPTH, width=120),
                TrackDefinition(
                    "curve",
                    "Curve",
                    TrackKind.CURVE,
                    width=220,
                    curve_mnemonics=["C1"],
                ),
                TrackDefinition(
                    "gas",
                    "Gas",
                    TrackKind.GAS,
                    width=180,
                    curve_mnemonics=["C1"],
                ),
            ],
            vertical_ruler_scale=VerticalRulerScaleSettings(
                major_step=5.0,
                minor_divisions=5,
            ),
        )
    )
    view.set_dataset(_dataset())
    qapp.processEvents()

    shared = view.shared_vertical_ruler_layout
    assert shared is not None
    axes = [
        view._rendered[track_id].plot.getAxis("left")
        for track_id in ("depth", "curve", "gas")
    ]
    assert all(isinstance(axis, TabletVerticalAxisItem) for axis in axes)
    typed_axes = [axis for axis in axes if isinstance(axis, TabletVerticalAxisItem)]
    assert all(axis.shared_layout is shared for axis in typed_axes)
    assert all(axis.isVisible() for axis in typed_axes)
    assert _axis_values(typed_axes[0]) == _axis_values(typed_axes[1])
    assert _axis_values(typed_axes[0]) == _axis_values(typed_axes[2])
    view.close()


def test_off_mode_hides_only_selected_column_and_keeps_common_depth(qapp) -> None:
    view = TabletView()
    view.set_layout_model(
        TabletLayout(
            tracks=[
                TrackDefinition("depth", "Depth", TrackKind.DEPTH, width=120),
                TrackDefinition(
                    "gas",
                    "Gas",
                    TrackKind.GAS,
                    width=180,
                    curve_mnemonics=["C1"],
                    vertical_ruler=VerticalRulerTrackSettings(
                        mode=VerticalRulerMode.OFF
                    ),
                ),
            ],
            vertical_ruler_scale=VerticalRulerScaleSettings(major_step=5.0),
        )
    )
    view.set_dataset(_dataset())

    shared = view.shared_vertical_ruler_layout
    depth_axis = view._rendered["depth"].plot.getAxis("left")
    gas_axis = view._rendered["gas"].plot.getAxis("left")
    assert shared is not None
    assert isinstance(depth_axis, TabletVerticalAxisItem)
    assert isinstance(gas_axis, TabletVerticalAxisItem)
    assert depth_axis.isVisible()
    assert depth_axis.shared_layout is shared
    assert not gas_axis.isVisible()
    assert gas_axis.shared_layout is None
    view.close()


def test_track_frequency_filters_only_values_from_shared_layout(qapp) -> None:
    settings = VerticalRulerTrackSettings(
        mode=VerticalRulerMode.LABELS_AND_TICKS,
        label_every_major=2,
        major_tick_every=2,
        minor_tick_every=3,
    )
    view = TabletView()
    view.set_layout_model(
        TabletLayout(
            tracks=[
                TrackDefinition("depth", "Depth", TrackKind.DEPTH, width=120),
                TrackDefinition(
                    "gas",
                    "Gas",
                    TrackKind.GAS,
                    width=180,
                    curve_mnemonics=["C1"],
                    vertical_ruler=settings,
                ),
            ],
            vertical_ruler_scale=VerticalRulerScaleSettings(
                major_step=5.0,
                minor_divisions=5,
            ),
        )
    )
    view.set_dataset(_dataset())

    shared = view.shared_vertical_ruler_layout
    gas_axis = view._rendered["gas"].plot.getAxis("left")
    assert shared is not None
    assert isinstance(gas_axis, TabletVerticalAxisItem)
    shared_values = {tick.value for tick in shared.ticks}
    rendered_values = _axis_values(gas_axis)
    assert rendered_values
    assert set(rendered_values).issubset(shared_values)
    assert len(rendered_values) < len(shared.ticks)
    assert _axis_labels(gas_axis) == ("1700", "1710", "1720", "1730", "1740", "1750")
    view.close()


def test_automatic_narrow_track_hides_labels_but_not_shared_tick_values(qapp) -> None:
    view = TabletView()
    view.set_layout_model(
        TabletLayout(
            tracks=[
                TrackDefinition("depth", "Depth", TrackKind.DEPTH, width=120),
                TrackDefinition(
                    "curve",
                    "Curve",
                    TrackKind.CURVE,
                    width=80,
                    curve_mnemonics=["C1"],
                ),
            ],
            vertical_ruler_scale=VerticalRulerScaleSettings(major_step=5.0),
        )
    )
    view.set_dataset(_dataset())

    depth_axis = view._rendered["depth"].plot.getAxis("left")
    curve_axis = view._rendered["curve"].plot.getAxis("left")
    assert isinstance(depth_axis, TabletVerticalAxisItem)
    assert isinstance(curve_axis, TabletVerticalAxisItem)
    assert curve_axis.isVisible()
    assert _axis_values(curve_axis) == _axis_values(depth_axis)
    assert _axis_labels(curve_axis) == ()
    assert _axis_labels(depth_axis)
    view.close()
''',
        encoding="utf-8",
    )


def update_plan() -> None:
    path = Path("docs/PROJECT_PLAN.md")
    text = path.read_text(encoding="utf-8")
    anchor = (
        "- [ ] **RULER-03:** использовать тот же resolved ruler в screen, preview, PDF и printer; "
        "добавить HiDPI/page-boundary regression tests.\n"
    )
    replacement = (
        "- [ ] **RULER-03:** экранный `TabletView` использует один resolved ruler и передаёт "
        "его точный набор значений/Y-координат всем глубинным и графическим колонкам; остаётся "
        "подключить тот же контракт к preview/PDF/printer и закрыть HiDPI/page-boundary tests.\n"
    )
    if anchor not in text:
        raise RuntimeError("PROJECT_PLAN.md: RULER-03 anchor not found")
    path.write_text(text.replace(anchor, replacement, 1), encoding="utf-8")


def main() -> None:
    patch_tablet_view()
    patch_existing_test()
    create_tests()
    update_plan()


if __name__ == "__main__":
    main()
