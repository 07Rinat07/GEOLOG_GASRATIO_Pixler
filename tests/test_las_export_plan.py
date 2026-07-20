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
    DatasetIndex,
    DatasetKind,
    DepthDomain,
    IndexRole,
    IndexType,
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


def test_export_analysis_warns_about_secondary_index_and_blocks_active_time() -> None:
    dataset = make_dataset()
    dataset.add_index(
        DatasetIndex(
            "time",
            "TIME",
            IndexType.RELATIVE_TIME,
            IndexRole.TIME,
            "s",
            np.array([0.0, 1.0]),
        ),
        make_active=True,
    )

    analysis = analyze_las_export(dataset, LasExportPlan())
    codes = {issue.code for issue in analysis.issues}

    assert not analysis.can_export
    assert "time-index-not-supported" in codes
    assert "additional-indexes-omitted" in codes


def test_export_analysis_reports_structured_multi_index_losses() -> None:
    dataset = make_dataset()
    dataset.add_index(
        DatasetIndex(
            "time-index",
            "DATE_TIME",
            IndexType.DATETIME,
            IndexRole.TIME,
            None,
            np.array(["2026-01-01", "2026-01-02"], dtype="datetime64[ns]"),
            timezone="UTC",
        )
    )
    dataset.add_index(
        DatasetIndex(
            "tvd-index",
            "TVD",
            IndexType.TVD,
            IndexRole.DEPTH,
            "m",
            np.array([99.0, 100.0]),
        )
    )

    analysis = analyze_las_export(dataset, LasExportPlan())

    assert analysis.can_export is True
    assert analysis.has_data_loss is True
    assert [loss.field_id for loss in analysis.losses] == ["time-index", "tvd-index"]
    assert analysis.losses[0].index_type is IndexType.DATETIME
    assert analysis.losses[0].sample_count == 2
    warning = next(issue for issue in analysis.issues if issue.code == "additional-indexes-omitted")
    assert "time-index" in warning.message
    assert "type=datetime" in warning.message
    assert "JSON или Parquet" in warning.message
