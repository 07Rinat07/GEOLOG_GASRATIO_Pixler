import numpy as np
import pytest

from geoworkbench.data.las_export_plan import (
    ExportIssueSeverity,
    LasExportPlan,
    LasExportVersion,
    analyze_las_export,
)
from geoworkbench.data.lossless_las import parse_lossless_las
from geoworkbench.domain.models import (
    CurveData,
    CurveMetadata,
    Dataset,
    DatasetKind,
    DepthDomain,
)


def make_dataset(*, domain: DepthDomain = DepthDomain.MD) -> Dataset:
    dataset = Dataset(
        "dataset-1",
        "Dataset",
        DatasetKind.GTI,
        domain,
        np.array([100.0, 101.0]),
    )
    dataset.curves["curve-1"] = CurveData(
        CurveMetadata("curve-1", "C1", "C1", "%", "Methane", dataset.dataset_id),
        np.array([1.0, np.nan]),
    )
    return dataset


def test_export_plan_validates_null_and_precision() -> None:
    with pytest.raises(ValueError, match="NULL"):
        LasExportPlan(null_value=np.nan)
    with pytest.raises(ValueError, match="Точность"):
        LasExportPlan(precision=0)
    with pytest.raises(ValueError, match="Точность"):
        LasExportPlan(precision=True)  # type: ignore[arg-type]
    with pytest.raises(ValueError, match="Версия"):
        LasExportPlan(version="3.0")  # type: ignore[arg-type]

    assert LasExportPlan(precision=7).number_format == "%.7f"


def test_export_analysis_reports_nan_substitution_as_warning() -> None:
    analysis = analyze_las_export(make_dataset(), LasExportPlan(null_value=-999.25))

    assert analysis.can_export
    assert any(issue.code == "missing-values-substituted" for issue in analysis.issues)


def test_export_analysis_blocks_time_index_and_null_collision() -> None:
    dataset = make_dataset(domain=DepthDomain.TIME)
    dataset.curves["curve-1"].values[0] = -999.25

    analysis = analyze_las_export(dataset, LasExportPlan(null_value=-999.25))
    codes = {issue.code for issue in analysis.errors}

    assert not analysis.can_export
    assert {"time-index-not-supported", "null-collision"} <= codes


def test_export_analysis_blocks_infinite_curve_values() -> None:
    dataset = make_dataset()
    dataset.curves["curve-1"].values[0] = np.inf

    analysis = analyze_las_export(dataset, LasExportPlan())

    assert not analysis.can_export
    assert any(issue.code == "infinite-curve-values" for issue in analysis.errors)


def test_export_analysis_detects_ambiguous_lossless_source() -> None:
    source = parse_lossless_las(b"~V\n~W\n~Well\n~C\n~A\n")

    analysis = analyze_las_export(make_dataset(), LasExportPlan(), source)

    assert not analysis.can_export
    issue = next(issue for issue in analysis.errors if issue.code == "ambiguous-source-sections")
    assert issue.severity is ExportIssueSeverity.ERROR


def test_las_1_2_plan_is_explicit_compatibility_warning() -> None:
    analysis = analyze_las_export(
        make_dataset(),
        LasExportPlan(version=LasExportVersion.V1_2),
    )

    assert analysis.can_export
    assert any(issue.code == "legacy-version" for issue in analysis.issues)
