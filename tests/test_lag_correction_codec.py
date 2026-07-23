from __future__ import annotations

import json
from dataclasses import asdict

import numpy as np
import pytest

from geoworkbench.domain.lag_correction import (
    ConstantTimeLagParameters,
    LagCorrectionMethod,
    LagCorrectionTarget,
)
from geoworkbench.domain.models import (
    CurveData,
    CurveMetadata,
    Dataset,
    DatasetIndex,
    DatasetKind,
    DepthDomain,
    IndexRole,
    IndexType,
    Project,
    TimeDepthAggregationPolicy,
    Well,
)
from geoworkbench.services.lag_correction import (
    LagCorrectionController,
    LagCorrectionCreateRequest,
)
from geoworkbench.storage.atomic_json import save_project
from geoworkbench.storage.project_codec import (
    PROJECT_FORMAT_VERSION,
    ProjectFormatError,
    load_project,
)


def make_project() -> Project:
    dataset = Dataset(
        "source",
        "Source",
        DatasetKind.GTI,
        DepthDomain.MD,
        np.array([10.0, 20.0, 30.0]),
    )
    dataset.add_index(
        DatasetIndex(
            "time",
            "TIME",
            IndexType.RELATIVE_TIME,
            IndexRole.TIME,
            "s",
            np.array([0.0, 10.0, 20.0]),
        )
    )
    dataset.curves["gas"] = CurveData(
        CurveMetadata("gas", "TGAS", "TGAS", "%", None, "source"),
        np.array([1.0, 2.0, 3.0]),
    )
    well = Well("well", "Well", datasets={"source": dataset})
    LagCorrectionController(well).create_profile(
        LagCorrectionCreateRequest(
            profile_id="lag",
            name="Gas lag",
            target=LagCorrectionTarget.GAS,
            source_dataset_id="source",
            source_time_index_id="time",
            source_depth_index_id="source:primary-index",
            target_curve_ids=("gas",),
            method=LagCorrectionMethod.CONSTANT_TIME,
            parameters=ConstantTimeLagParameters(10.0),
            aggregation_policy=TimeDepthAggregationPolicy.ERROR,
            output_dataset_id="corrected",
            output_source_index_id="corrected:source",
            output_index_id="corrected:axis",
            created_at="2026-07-23T10:00:00Z",
            created_by="Rinat",
        )
    )
    return Project("project", "Project", wells={"well": well})


def test_lag_correction_round_trip_and_project_format_v19(tmp_path) -> None:
    target = tmp_path / "lag.geolog.json"
    save_project(make_project(), target)

    loaded = load_project(target)
    profile = loaded.wells["well"].lag_correction_profiles["lag"]

    assert PROJECT_FORMAT_VERSION == 19
    assert json.loads(target.read_text(encoding="utf-8"))["format_version"] == 19
    assert profile.active.method is LagCorrectionMethod.CONSTANT_TIME
    assert profile.active.parameters == ConstantTimeLagParameters(10.0)
    np.testing.assert_allclose(
        loaded.wells["well"].datasets["corrected"].indexes["corrected:axis"].values,
        [np.nan, 10.0, 20.0],
        equal_nan=True,
    )


def test_codec_rejects_unknown_parameter_key_and_tampered_output(tmp_path) -> None:
    target = tmp_path / "lag.geolog.json"
    save_project(make_project(), target)
    raw = json.loads(target.read_text(encoding="utf-8"))
    revision = raw["project"]["wells"]["well"]["lag_correction_profiles"]["lag"]["revisions"][0]
    revision["parameters"]["unexpected"] = 1
    target.write_text(json.dumps(raw), encoding="utf-8")
    with pytest.raises(ProjectFormatError, match="lag parameters|параметры lag correction"):
        load_project(target)

    save_project(make_project(), target)
    raw = json.loads(target.read_text(encoding="utf-8"))
    raw["project"]["wells"]["well"]["datasets"]["corrected"]["curves"]["gas"]["values"][0] = 99.0
    target.write_text(json.dumps(raw), encoding="utf-8")
    with pytest.raises(ProjectFormatError, match="persisted projection"):
        load_project(target)


def test_codec_rejects_non_contiguous_revisions(tmp_path) -> None:
    target = tmp_path / "lag.geolog.json"
    save_project(make_project(), target)
    raw = json.loads(target.read_text(encoding="utf-8"))
    revisions = raw["project"]["wells"]["well"]["lag_correction_profiles"]["lag"][
        "revisions"
    ]
    revisions[0]["revision"] = 3
    target.write_text(json.dumps(raw), encoding="utf-8")

    with pytest.raises(ProjectFormatError, match="lag correction profile"):
        load_project(target)
