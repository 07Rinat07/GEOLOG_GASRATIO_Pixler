from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace
from typing import cast

import numpy as np
import pytest

from geoworkbench.data.las_adapter import LasImportResult
from geoworkbench.data.lossless_las import parse_lossless_las
from geoworkbench.domain.models import (
    CurveData,
    CurveMetadata,
    Dataset,
    DatasetKind,
    DepthDomain,
    Project,
    Well,
)
from geoworkbench.project.daily_las_growth_controller import DailyLasGrowthController
from geoworkbench.project.session import ProjectSession
from geoworkbench.services.daily_las_growth import (
    analyze_daily_las_growth,
    file_sha256,
)


def _dataset(dataset_id: str, depth: list[float], values: list[float]) -> Dataset:
    curve_id = f"{dataset_id}:rop"
    return Dataset(
        dataset_id=dataset_id,
        name=dataset_id,
        kind=DatasetKind.GTI,
        depth_domain=DepthDomain.MD,
        depth=np.asarray(depth, dtype=np.float64),
        curves={
            curve_id: CurveData(
                CurveMetadata(
                    curve_id=curve_id,
                    original_mnemonic="ROP",
                    canonical_mnemonic="ROP",
                    unit="m/h",
                    description="Rate of penetration",
                    source_dataset_id=dataset_id,
                ),
                np.asarray(values, dtype=np.float64),
            )
        },
        headers={"STRT": str(depth[0]), "STOP": str(depth[-1]), "STEP": "1"},
    )


def _arm_controller(
    controller: DailyLasGrowthController,
    *,
    source_path: Path,
    source_result: LasImportResult,
    plan: object,
) -> None:
    controller._source = source_result
    controller._source_path = source_path
    controller._plan = plan  # type: ignore[assignment]
    controller._provider_kind = "manual_file"
    controller._provider_location = str(source_path)


def test_post_ingest_failure_rolls_back_only_new_append_and_allows_retry(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    target = _dataset("target", [100.0, 101.0], [10.0, 11.0])
    incoming = _dataset("incoming", [101.0, 102.0], [11.0, 12.0])
    unrelated = _dataset("unrelated", [200.0, 201.0], [20.0, 21.0])
    well = Well(
        "well-1",
        "Well",
        datasets={target.dataset_id: target, unrelated.dataset_id: unrelated},
    )
    initial_document = parse_lossless_las(b"~A\n100 10\n101 11\n")
    unrelated_document = parse_lossless_las(b"~A\n200 20\n201 21\n")
    session = ProjectSession(
        project=Project("project-1", "Project", wells={well.well_id: well}),
        current_well_id=well.well_id,
        current_dataset_id=target.dataset_id,
        source_documents={
            target.dataset_id: initial_document,
            "unrelated-artifact": unrelated_document,
        },
    )
    controller = DailyLasGrowthController(session)

    source_path = tmp_path / "daily.las"
    raw_source = b"daily-source-revision"
    source_path.write_bytes(raw_source)
    source_document = parse_lossless_las(raw_source)
    source_result = cast(
        LasImportResult,
        SimpleNamespace(dataset=incoming, source_document=source_document),
    )
    plan = analyze_daily_las_growth(
        target,
        incoming,
        source_name=source_path.name,
        source_sha256=file_sha256(source_path),
    )
    _arm_controller(
        controller,
        source_path=source_path,
        source_result=source_result,
        plan=plan,
    )

    original_index = target.active_index
    original_curve = target.curve_by_mnemonic("ROP")
    assert original_curve is not None
    original_depth = target.depth.copy()
    original_index_values = original_index.values.copy()
    original_curve_values = original_curve.values.copy()
    original_headers = dict(target.headers)
    original_preserve = controller._preserve_initial_source

    def fail_after_initial_source_preserved(dataset: Dataset) -> None:
        original_preserve(dataset)
        raise RuntimeError("post-ingest assembly failed")

    monkeypatch.setattr(
        controller,
        "_preserve_initial_source",
        fail_after_initial_source_preserved,
    )

    with pytest.raises(RuntimeError, match="post-ingest assembly failed"):
        controller.apply(plan)

    assert target.active_index is original_index
    assert target.curve_by_mnemonic("ROP") is original_curve
    np.testing.assert_array_equal(target.depth, original_depth)
    np.testing.assert_array_equal(target.active_index.values, original_index_values)
    np.testing.assert_array_equal(original_curve.values, original_curve_values)
    assert original_curve.version == 1
    assert target.headers == original_headers
    assert target.append_history == []
    assert target.source_revisions == []
    assert session.source_documents == {
        target.dataset_id: initial_document,
        "unrelated-artifact": unrelated_document,
    }
    assert well.datasets[unrelated.dataset_id] is unrelated
    assert session.dirty is False

    monkeypatch.setattr(controller, "_preserve_initial_source", original_preserve)
    _arm_controller(
        controller,
        source_path=source_path,
        source_result=source_result,
        plan=plan,
    )
    outcome = controller.apply(plan)

    assert outcome.record is not None
    assert outcome.record.rows_added == 1
    np.testing.assert_array_equal(target.depth, np.asarray([100.0, 101.0, 102.0]))
    assert len(target.source_revisions) == 2
    assert source_document.sha256 in {
        document.sha256 for document in session.source_documents.values()
    }
    assert session.source_documents["unrelated-artifact"] is unrelated_document
    assert session.dirty is True
