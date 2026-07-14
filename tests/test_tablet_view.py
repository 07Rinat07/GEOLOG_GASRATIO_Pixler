import numpy as np
import pytest

from geoworkbench.domain.models import (
    CurveData,
    CurveMetadata,
    Dataset,
    DatasetKind,
    DepthDomain,
)
from geoworkbench.tablet.models import TabletLayout, TrackDefinition, TrackKind, XScale
from geoworkbench.tablet.tablet_view import TabletView, curve_legend_label


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
