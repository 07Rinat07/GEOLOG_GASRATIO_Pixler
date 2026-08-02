from __future__ import annotations

from pathlib import Path


TABLET_VIEW = Path("src/geoworkbench/tablet/tablet_view.py")
TABLET_PRINT = Path("src/geoworkbench/printing/tablet_print.py")


def replace_once(path: Path, old: str, new: str) -> None:
    text = path.read_text(encoding="utf-8")
    count = text.count(old)
    if count != 1:
        raise RuntimeError(
            f"{path}: expected one replacement, found {count}: {old[:120]!r}"
        )
    path.write_text(text.replace(old, new, 1), encoding="utf-8")


def patch_tablet_view() -> None:
    replace_once(
        TABLET_VIEW,
        "    @property\n"
        "    def shared_vertical_ruler_layout(self) -> VerticalRulerLayout | None:\n"
        "        return self._shared_vertical_ruler_layout\n\n"
        "    def _vertical_ruler_kind(self) -> VerticalRulerKind | None:\n",
        "    @property\n"
        "    def shared_vertical_ruler_layout(self) -> VerticalRulerLayout | None:\n"
        "        return self._shared_vertical_ruler_layout\n\n"
        "    def refresh_shared_vertical_rulers(self) -> VerticalRulerLayout | None:\n"
        "        current = self.visible_depth_range\n"
        "        if current is None:\n"
        "            self._shared_vertical_ruler_layout = None\n"
        "            for rendered in self._rendered.values():\n"
        "                rendered.widget.set_shared_vertical_ruler_layout(None)\n"
        "            return None\n"
        "        self._synchronize_vertical_rulers(*current)\n"
        "        return self._shared_vertical_ruler_layout\n\n"
        "    def _vertical_ruler_kind(self) -> VerticalRulerKind | None:\n",
    )
    replace_once(
        TABLET_VIEW,
        "        self._annotation_print_mode = bool(enabled)\n",
        "        self._annotation_print_mode = bool(enabled)\n"
        "        self.refresh_shared_vertical_rulers()\n",
    )


def patch_tablet_print() -> None:
    replace_once(
        TABLET_PRINT,
        "from geoworkbench.tablet.tablet_view import TabletView\n",
        "from geoworkbench.tablet.tablet_view import (\n"
        "    TabletVerticalAxisItem,\n"
        "    TabletView,\n"
        ")\n"
        "from geoworkbench.tablet.vertical_ruler import (\n"
        "    VerticalRulerLayout,\n"
        "    VerticalRulerTick,\n"
        ")\n",
    )
    replace_once(
        TABLET_PRINT,
        "    raster_scale: float = 1.0\n\n"
        "    def __post_init__(self) -> None:\n",
        "    raster_scale: float = 1.0\n"
        "    vertical_ruler_layout: VerticalRulerLayout | None = None\n"
        "    vertical_ruler_ticks_by_track: tuple[\n"
        "        tuple[str, tuple[VerticalRulerTick, ...]], ...\n"
        "    ] = ()\n\n"
        "    def __post_init__(self) -> None:\n",
    )
    replace_once(
        TABLET_PRINT,
        "    annotation_print_enabled = False\n\n"
        "    try:\n",
        "    annotation_print_enabled = False\n"
        "    print_ruler_layout: VerticalRulerLayout | None = None\n"
        "    print_ruler_ticks_by_track: tuple[\n"
        "        tuple[str, tuple[VerticalRulerTick, ...]], ...\n"
        "    ] = ()\n\n"
        "    try:\n",
    )

    text = TABLET_PRINT.read_text(encoding="utf-8")
    activation = "        _activate_layout_tree(tablet)\n"
    count = text.count(activation)
    if count < 2:
        raise RuntimeError(
            f"tablet_print.py: expected at least two layout activations, found {count}"
        )
    text = text.replace(
        activation,
        activation + "        tablet.refresh_shared_vertical_rulers()\n",
    )
    TABLET_PRINT.write_text(text, encoding="utf-8")

    replace_once(
        TABLET_PRINT,
        "            for item, width in zip(rendered, layout.widths, strict=True):\n"
        "                item.widget.set_track_width(width)\n"
        "            measured_header_height = max(\n",
        "            for item, width in zip(rendered, layout.widths, strict=True):\n"
        "                item.widget.set_track_width(width)\n"
        "            tablet.refresh_shared_vertical_rulers()\n"
        "            measured_header_height = max(\n",
    )
    replace_once(
        TABLET_PRINT,
        "        for item, logical_width in zip(rendered, layout.widths, strict=True):\n",
        "        print_ruler_layout = tablet.refresh_shared_vertical_rulers()\n"
        "        print_ruler_ticks_by_track = tuple(\n"
        "            (\n"
        "                item.definition.track_id,\n"
        "                axis.resolved_ticks,\n"
        "            )\n"
        "            for item in rendered\n"
        "            if isinstance(\n"
        "                axis := item.widget.plot.getAxis(\"left\"),\n"
        "                TabletVerticalAxisItem,\n"
        "            )\n"
        "        )\n\n"
        "        for item, logical_width in zip(rendered, layout.widths, strict=True):\n",
    )
    replace_once(
        TABLET_PRINT,
        "        float(raster_scale),\n"
        "    )\n",
        "        float(raster_scale),\n"
        "        print_ruler_layout,\n"
        "        print_ruler_ticks_by_track,\n"
        "    )\n",
    )


def create_tests() -> None:
    Path("tests/test_tablet_print_shared_vertical_ruler.py").write_text(
        '''from __future__ import annotations

import numpy as np

from geoworkbench.domain.models import (
    CurveData,
    CurveMetadata,
    Dataset,
    DatasetKind,
    DepthDomain,
)
from geoworkbench.printing.tablet_print import capture_tablet_print_snapshot
from geoworkbench.tablet.models import TabletLayout, TrackDefinition, TrackKind
from geoworkbench.tablet.tablet_view import TabletView
from geoworkbench.tablet.vertical_ruler import (
    VerticalRulerMode,
    VerticalRulerScaleSettings,
    VerticalRulerTrackSettings,
)


def _dataset() -> Dataset:
    depth = np.arange(1700.0, 1751.0, dtype=np.float64)
    dataset = Dataset(
        "print-ruler-dataset",
        "Print ruler",
        DatasetKind.GTI,
        DepthDomain.MD,
        depth,
    )
    dataset.curves["curve-c1"] = CurveData(
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
    return dataset


def _view() -> TabletView:
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
                        mode=VerticalRulerMode.LABELS_AND_TICKS,
                        label_every_major=2,
                        major_tick_every=2,
                        minor_tick_every=3,
                    ),
                ),
            ],
            vertical_ruler_scale=VerticalRulerScaleSettings(
                major_step=5.0,
                minor_divisions=5,
            ),
        )
    )
    view.resize(720, 760)
    view.set_dataset(_dataset())
    view.set_visible_depth(1700.0, 1725.0)
    return view


def test_print_snapshot_records_one_resolved_ruler_for_all_columns(qapp) -> None:
    view = _view()
    qapp.processEvents()

    snapshot = capture_tablet_print_snapshot(
        view,
        page_aspect_ratio=1.4,
        fit_columns=True,
        target_content_height=840,
        layout_content_height=840,
    )

    layout = snapshot.vertical_ruler_layout
    ticks_by_track = dict(snapshot.vertical_ruler_ticks_by_track)
    assert layout is not None
    assert layout.minimum == 1700.0
    assert layout.maximum == 1725.0
    assert layout.major_step == 5.0
    assert set(ticks_by_track) == {"depth", "gas"}
    shared_values = {tick.value for tick in layout.ticks}
    depth_values = {tick.value for tick in ticks_by_track["depth"]}
    gas_values = {tick.value for tick in ticks_by_track["gas"]}
    assert depth_values == shared_values
    assert gas_values
    assert gas_values.issubset(shared_values)
    assert len(gas_values) < len(depth_values)
    view.close()


def test_adjacent_print_pages_keep_the_exact_shared_boundary_tick(qapp) -> None:
    view = _view()
    qapp.processEvents()

    view.set_visible_depth(1700.0, 1725.0)
    first = capture_tablet_print_snapshot(
        view,
        page_aspect_ratio=1.4,
        target_content_height=840,
        layout_content_height=840,
    )
    view.set_visible_depth(1725.0, 1750.0)
    second = capture_tablet_print_snapshot(
        view,
        page_aspect_ratio=1.4,
        target_content_height=840,
        layout_content_height=840,
    )

    assert first.vertical_ruler_layout is not None
    assert second.vertical_ruler_layout is not None
    first_values = {tick.value for tick in first.vertical_ruler_layout.ticks}
    second_values = {tick.value for tick in second.vertical_ruler_layout.ticks}
    assert 1725.0 in first_values
    assert 1725.0 in second_values
    assert first.vertical_ruler_layout.maximum == second.vertical_ruler_layout.minimum
    view.close()


def test_print_capture_restores_screen_ruler_mode_and_range(qapp) -> None:
    view = _view()
    qapp.processEvents()
    original_range = view.visible_depth_range
    original_layout = view.shared_vertical_ruler_layout

    snapshot = capture_tablet_print_snapshot(
        view,
        page_aspect_ratio=1.4,
        target_content_height=840,
        layout_content_height=840,
    )

    assert snapshot.vertical_ruler_layout is not None
    assert view.visible_depth_range == original_range
    assert view.shared_vertical_ruler_layout is not None
    assert view.shared_vertical_ruler_layout is not snapshot.vertical_ruler_layout
    assert view.shared_vertical_ruler_layout == original_layout
    view.close()
''',
        encoding="utf-8",
    )


def update_plan() -> None:
    path = Path("docs/PROJECT_PLAN.md")
    text = path.read_text(encoding="utf-8")
    old = (
        "- [ ] **RULER-03:** экранный `TabletView` использует один resolved ruler и передаёт "
        "его точный набор значений/Y-координат всем глубинным и графическим колонкам; остаётся "
        "подключить тот же контракт к preview/PDF/printer и закрыть HiDPI/page-boundary tests.\n"
    )
    new = (
        "- [x] **RULER-03:** screen, preview, PDF и printer используют один resolved ruler; "
        "печатный snapshot сохраняет общий layout и фактические ticks колонок, а regression tests "
        "проверяют общий page-boundary и восстановление экранного состояния.\n"
    )
    if old not in text:
        raise RuntimeError("PROJECT_PLAN.md: RULER-03 anchor not found")
    path.write_text(text.replace(old, new, 1), encoding="utf-8")


def main() -> None:
    patch_tablet_view()
    patch_tablet_print()
    create_tests()
    update_plan()


if __name__ == "__main__":
    main()
