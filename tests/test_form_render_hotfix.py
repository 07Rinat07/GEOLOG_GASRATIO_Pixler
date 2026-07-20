from __future__ import annotations

import numpy as np

from geoworkbench.domain.models import (
    CurveData,
    CurveMetadata,
    Dataset,
    DatasetKind,
    DepthDomain,
)
from geoworkbench.forms import FormApplyEngine, factory_templates
from geoworkbench.tablet.models import TabletLayout, TrackDefinition, TrackKind
from geoworkbench.tablet.tablet_view import TabletView


def _dataset() -> Dataset:
    dataset = Dataset(
        "render-hotfix",
        "LAS render hotfix",
        DatasetKind.GTI,
        DepthDomain.MD,
        np.array([1000.0, 1000.5, 1001.0]),
    )
    for position, (mnemonic, canonical, description, unit) in enumerate(
        (
            ("ROP_AVG", "ROP", "Скорость проходки", "m/h"),
            ("TGAS", "TOTAL_GAS", "Суммарный газ", "%"),
            ("C1", "C1", "Метан", "%"),
            ("GR", "GR", "Гамма-каротаж", "API"),
        )
    ):
        metadata = CurveMetadata(
            curve_id=f"curve-{position}",
            original_mnemonic=mnemonic,
            canonical_mnemonic=canonical,
            unit=unit,
            description=description,
            source_dataset_id=dataset.dataset_id,
        )
        dataset.curves[metadata.curve_id] = CurveData(
            metadata,
            np.array([float(position + 1), float(position + 2), float(position + 3)]),
        )
    return dataset


def test_default_tablet_renders_curve_without_explicit_style(qapp) -> None:
    dataset = _dataset()
    view = TabletView()
    view.set_layout_model(
        TabletLayout(
            [
                TrackDefinition(
                    "default-curves",
                    "Default curves",
                    TrackKind.CURVE,
                    curve_mnemonics=["ROP_AVG", "TGAS"],
                )
            ]
        )
    )

    view.set_dataset(dataset)
    qapp.processEvents()

    rendered = view._rendered["default-curves"]
    assert set(rendered.curve_items or {}) == {"ROP_AVG", "TGAS"}
    view.close()


def test_factory_depth_form_renders_real_las_curves(qapp) -> None:
    dataset = _dataset()
    result = FormApplyEngine().build_layout(
        factory_templates("ru")["factory-depth-basic"],
        dataset,
    )
    view = TabletView()

    view.set_layout_model(result.layout)
    view.set_dataset(dataset)
    qapp.processEvents()

    rendered_mnemonics = {
        mnemonic
        for rendered in view._rendered.values()
        for mnemonic in (rendered.curve_items or {})
    }
    assert rendered_mnemonics == {"ROP_AVG", "TGAS", "C1", "GR"}
    assert result.resolved_count == 4
    view.close()
