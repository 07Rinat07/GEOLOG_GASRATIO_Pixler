import numpy as np
import pyqtgraph as pg
import pytest

from geoworkbench.domain.models import (
    CanvasObject,
    CurveData,
    CurveMetadata,
    Dataset,
    DatasetKind,
    DepthDomain,
    LithologyInterval,
)
from geoworkbench.project.lithotype_catalog_controller import CatalogLithotype
from geoworkbench.tablet.models import TabletLayout, TrackDefinition, TrackKind, XScale
from geoworkbench.tablet.tablet_view import TabletTrackWidget, TabletView, curve_legend_label


def make_curve(dataset_id: str, mnemonic: str, unit: str | None) -> CurveData:
    return CurveData(
        CurveMetadata(
            f"curve-{mnemonic}",
            mnemonic,
            mnemonic,
            unit,
            None,
            dataset_id,
        ),
        np.array([1.0, 2.0]),
    )


def test_curve_legend_label_includes_unit_only_when_present() -> None:
    assert curve_legend_label(make_curve("dataset", "C1", "%")) == "C1 [%]"
    assert curve_legend_label(make_curve("dataset", "ROP", None)) == "ROP"
    assert curve_legend_label(make_curve("dataset", "GR", "  API  ")) == "GR [API]"


def test_tablet_view_exposes_rendered_legend_labels(qapp) -> None:
    dataset = Dataset(
        "dataset-1",
        "Dataset",
        DatasetKind.GTI,
        DepthDomain.MD,
        np.array([100.0, 101.0]),
    )
    c1 = make_curve(dataset.dataset_id, "C1", "%")
    rop = make_curve(dataset.dataset_id, "ROP", None)
    dataset.curves = {c1.metadata.curve_id: c1, rop.metadata.curve_id: rop}
    view = TabletView()
    view.set_layout_model(
        TabletLayout(
            [
                TrackDefinition(
                    "curves",
                    "Curves",
                    TrackKind.CURVE,
                    curve_mnemonics=["C1", "ROP"],
                )
            ]
        )
    )

    view.set_dataset(dataset)
    qapp.processEvents()

    assert view.legend_labels("curves") == ("C1 [%]", "ROP")
    view.close()


def test_logarithmic_track_omits_curve_without_positive_values(qapp) -> None:
    dataset = Dataset(
        "dataset-1",
        "Dataset",
        DatasetKind.GTI,
        DepthDomain.MD,
        np.array([100.0, 101.0]),
    )
    curve = make_curve(dataset.dataset_id, "ZERO", None)
    curve.values = np.array([0.0, -1.0])
    dataset.curves[curve.metadata.curve_id] = curve
    view = TabletView()
    view.set_layout_model(
        TabletLayout(
            [
                TrackDefinition(
                    "log",
                    "Log",
                    TrackKind.CURVE,
                    curve_mnemonics=["ZERO"],
                    x_scale=XScale.LOGARITHMIC,
                )
            ]
        )
    )

    view.set_dataset(dataset)
    qapp.processEvents()

    assert view.legend_labels("log") == ()
    view.close()


def test_tablet_view_restores_saved_visible_depth_without_emitting_change(qapp) -> None:
    dataset = Dataset(
        "dataset-1",
        "Dataset",
        DatasetKind.GTI,
        DepthDomain.MD,
        np.array([100.0, 150.0, 200.0]),
    )
    view = TabletView()
    emitted: list[tuple[float, float]] = []
    view.visible_depth_changed.connect(lambda top, bottom: emitted.append((top, bottom)))
    view.set_layout_model(
        TabletLayout(
            [TrackDefinition("depth", "Глубина", TrackKind.DEPTH)],
            visible_depth_top=120.0,
            visible_depth_bottom=160.0,
        )
    )

    view.set_dataset(dataset)
    qapp.processEvents()

    assert view.visible_depth_range == pytest.approx((120.0, 160.0))
    assert emitted == []
    view.close()


def test_tablet_view_limits_points_and_updates_them_for_visible_depth(qapp) -> None:
    depth = np.arange(20_000, dtype=np.float64)
    dataset = Dataset(
        "dataset-1",
        "Large Dataset",
        DatasetKind.GTI,
        DepthDomain.MD,
        depth,
    )
    curve = make_curve(dataset.dataset_id, "ROP", "m/h")
    curve.values = depth * 0.1
    dataset.curves[curve.metadata.curve_id] = curve
    view = TabletView()
    view.set_layout_model(
        TabletLayout(
            [
                TrackDefinition(
                    "curve",
                    "ROP",
                    TrackKind.CURVE,
                    curve_mnemonics=["ROP"],
                )
            ]
        )
    )

    view.set_dataset(dataset)
    qapp.processEvents()
    full_count = view.rendered_curve_point_count("curve", "ROP")
    emitted: list[tuple[float, float]] = []
    view.visible_depth_changed.connect(lambda top, bottom: emitted.append((top, bottom)))
    view.set_visible_depth(100.0, 200.0)
    qapp.processEvents()

    assert full_count == 5000
    assert view.rendered_curve_point_count("curve", "ROP") == 101
    assert emitted == []
    view.close()


def test_user_depth_change_updates_samples_and_linked_tracks(qapp) -> None:
    depth = np.arange(1000, dtype=np.float64)
    dataset = Dataset(
        "dataset-1",
        "Dataset",
        DatasetKind.GTI,
        DepthDomain.MD,
        depth,
    )
    curve = make_curve(dataset.dataset_id, "ROP", "m/h")
    curve.values = depth
    dataset.curves[curve.metadata.curve_id] = curve
    view = TabletView()
    view.set_layout_model(
        TabletLayout(
            [
                TrackDefinition("depth", "Глубина", TrackKind.DEPTH),
                TrackDefinition(
                    "curve",
                    "ROP",
                    TrackKind.CURVE,
                    curve_mnemonics=["ROP"],
                ),
            ]
        )
    )
    emitted: list[tuple[float, float]] = []
    view.visible_depth_changed.connect(lambda top, bottom: emitted.append((top, bottom)))
    view.resize(800, 600)
    view.show()
    view.set_dataset(dataset)
    qapp.processEvents()
    depth_widget = view.findChild(TabletTrackWidget, "track-depth")
    assert depth_widget is not None
    master_plot = depth_widget.findChild(pg.PlotWidget)
    assert master_plot is not None

    master_plot.setYRange(100.0, 200.0, padding=0)
    qapp.processEvents()

    assert emitted[-1] == pytest.approx((100.0, 200.0))
    assert view.track_depth_range("depth") == pytest.approx((100.0, 200.0))
    assert view.track_depth_range("curve") == pytest.approx((100.0, 200.0))
    assert view.rendered_curve_point_count("curve", "ROP") == 101
    view.close()


def test_tablet_view_renders_depth_annotations_on_every_track(qapp) -> None:
    dataset = Dataset(
        "dataset-1",
        "Dataset",
        DatasetKind.GTI,
        DepthDomain.MD,
        np.array([100.0, 150.0, 200.0]),
    )
    view = TabletView()
    view.set_layout_model(
        TabletLayout(
            [
                TrackDefinition("depth", "Глубина", TrackKind.DEPTH),
                TrackDefinition("curve", "Curve", TrackKind.CURVE),
            ]
        )
    )
    view.set_canvas_objects(
        [
            CanvasObject(
                "note-1",
                "depth_annotation",
                "depth",
                0.0,
                150.0,
                1.0,
                0.0,
                top_depth=150.0,
                bottom_depth=150.0,
                properties={"text": "Газопроявление"},
            )
        ]
    )

    view.set_dataset(dataset)
    qapp.processEvents()

    assert view.rendered_annotation_ids("depth") == ("note-1",)
    assert view.rendered_annotation_ids("curve") == ("note-1",)
    view.close()


def test_tablet_view_renders_lithology_intervals(qapp) -> None:
    dataset = Dataset(
        "dataset-1",
        "Dataset",
        DatasetKind.GTI,
        DepthDomain.MD,
        np.array([100.0, 150.0, 200.0]),
    )
    view = TabletView()
    view.set_layout_model(
        TabletLayout([TrackDefinition("lithology", "Литология", TrackKind.LITHOLOGY)])
    )
    view.set_lithology(
        [LithologyInterval("layer-1", 110.0, 160.0, "sandstone", "Песчаник")],
        (
            CatalogLithotype(
                "sandstone",
                "SS",
                "Песчаник",
                "Sandstone",
                "sedimentary",
                "#e7cf8b",
                "sandstone_bricks",
                True,
            ),
        ),
    )

    view.set_dataset(dataset)
    qapp.processEvents()

    assert view.rendered_lithology_ids("lithology") == ("layer-1",)
    view.close()
