from __future__ import annotations

import numpy as np

from geoworkbench.domain.models import (
    CurveData,
    CurveMetadata,
    Dataset,
    DatasetKind,
    DepthDomain,
)
from geoworkbench.project.session import ProjectSession
from geoworkbench.services.import_review import ImportReviewController
from geoworkbench.services.semantic_channels import SemanticChannelDictionary
from geoworkbench.tablet.controller import TabletController


def _large_mixed_dataset() -> Dataset:
    depth = 47.0 + np.arange(9847, dtype=np.float64) * 0.2
    dataset = Dataset(
        "mixed-9847",
        "Геология_plus_Технология",
        DatasetKind.GTI,
        DepthDomain.MD,
        depth,
    )
    names = [
        "ГЛУБИНА_СКВАЖИНЫ:1",
        "ГЛУБИНА_КОН:1",
        "КОД_ПОРОДЫ",
        "ГЛУБИНА_СКВАЖИНЫ:2",
        "ГЛУБИНА_КОН:2",
        "ПОРОДА1_КОД",
        "ПОРОДА1_КОЛИЧ",
        "CACO3_(КАЛЬЦИТ)",
        "INTENSITY_LBA",
        "C1",
        "C2",
        "C3",
        "C4",
        "C5",
        "IC4",
        "IC5",
        "СУММА_ГАЗОВ",
        "S123456",
        "S200",
        "S300",
        "S720",
        "S800",
        "S900",
        "S1200",
        "S50",
        "S51",
        "S1001",
        "S106",
        "S107",
        "S202",
        "C1_C2",
        "C1_C3",
        "C2_C3",
        "C1_C2C3",
        "TG_CALC",
        "C1_REL",
        "C2_REL",
        "C3_REL",
        "IC4_REL",
        "C4_REL",
        "IC5_REL",
        "C5_REL",
        "S123456_TEHNOLOGIYA",
        "S200_TEHNOLOGIYA",
        "S300_TEHNOLOGIYA",
        "S720_TEHNOLOGIYA",
        "S800_TEHNOLOGIYA",
        "S900_TEHNOLOGIYA",
        "S1200_TEHNOLOGIYA",
        "S50_TEHNOLOGIYA",
        "S51_TEHNOLOGIYA",
        "S1001_TEHNOLOGIYA",
        "S106_TEHNOLOGIYA",
        "S107_TEHNOLOGIYA",
        "S202_TEHNOLOGIYA",
        "TIME",
        "SPID",
        "TENS",
        "METKA",
        "DTIME",
        "MARKER",
        "CALI",
        "GK_1",
        "NNKBZ",
        "NNKMZ",
        "ПОРОДА2_КОД",
        "ПОРОДА2_КОЛИЧ",
        "ПОРОДА3_КОД",
        "ПОРОДА3_КОЛИЧ",
        "ПОРОДА4_КОД",
        "ПОРОДА4_КОЛИЧ",
        "ПОРОДА5_КОД",
        "ПОРОДА5_КОЛИЧ",
    ]
    dictionary = SemanticChannelDictionary()
    for index, name in enumerate(names):
        binding = dictionary.resolve(name, unit="")
        curve_id = f"curve-{index}"
        dataset.curves[curve_id] = CurveData(
            CurveMetadata(
                curve_id,
                name,
                binding.canonical_mnemonic,
                None,
                None,
                dataset.dataset_id,
                semantic=binding,
            ),
            np.full(depth.shape, float(index), dtype=np.float64),
        )
    return dataset


def test_large_cyrillic_mixed_las_warnings_do_not_block_review_or_layout() -> None:
    dataset = _large_mixed_dataset()
    review_controller = ImportReviewController()

    committed = review_controller.commit(
        dataset, review_controller.initial_plan(dataset)
    )

    assert committed.review.error_count == 0
    assert len(committed.dataset.curves) == 73

    session = ProjectSession()
    session.add_dataset(committed.dataset, create_new_well=True)
    layout = TabletController(session).build_default_layout()

    assert layout.tracks
    assert sum(len(track.curve_mnemonics) for track in layout.tracks) <= 12
