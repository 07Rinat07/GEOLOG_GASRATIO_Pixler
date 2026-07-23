from __future__ import annotations

import numpy as np
import pytest

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
from geoworkbench.services.report_definition import (
    ReportDefinition,
    ReportDefinitionError,
    ReportIntervalContext,
    ReportIntervalMode,
    ReportIntervalSelection,
    ReportProfile,
    ReportSectionDefinition,
    ReportSectionKind,
    resolve_report_definition,
)


def make_dataset() -> Dataset:
    dataset = Dataset(
        "dataset-1",
        "Well A",
        DatasetKind.GTI,
        DepthDomain.MD,
        np.array([1000.0, 1001.0, np.nan, 1003.0, 1004.0]),
    )
    dataset.curves = {
        "curve-c1": CurveData(
            CurveMetadata("curve-c1", "C1", "C1", "ppm", "Methane", dataset.dataset_id),
            np.array([1.0, 2.0, np.nan, 4.0, 5.0]),
        ),
        "curve-rop": CurveData(
            CurveMetadata("curve-rop", "ROP", "ROP", "m/h", "ROP", dataset.dataset_id),
            np.array([10.0, 11.0, 12.0, 13.0, 14.0]),
        ),
    }
    return dataset


def definition(interval: ReportIntervalSelection) -> ReportDefinition:
    return ReportDefinition(
        definition_id="report-1",
        name="Combined report",
        profile=ReportProfile.COMBINED,
        dataset_id="dataset-1",
        index_id="dataset-1:primary-index",
        interval=interval,
        language="RU",
        curve_ids=("curve-c1",),
        sections=(
            ReportSectionDefinition(ReportSectionKind.DRILLING, curve_ids=("curve-rop",)),
        ),
        form_kind="tablet-layout",
        form_id="dataset-1",
        form_revision="schema:14/content:abc",
    )


def test_definition_is_deterministic_and_unifies_section_curves() -> None:
    item = definition(ReportIntervalSelection(ReportIntervalMode.FULL))

    assert item.language == "ru"
    assert item.selected_curve_ids == ("curve-c1", "curve-rop")
    assert item.content_sha256 == definition(
        ReportIntervalSelection(ReportIntervalMode.FULL)
    ).content_sha256
    assert item.payload()["profile"] == "combined"


def test_custom_interval_is_clamped_and_inclusive() -> None:
    resolved = resolve_report_definition(
        make_dataset(),
        definition(ReportIntervalSelection(ReportIntervalMode.CUSTOM, 999.0, 1003.5)),
    )

    assert resolved.interval.bounds == (1000.0, 1003.5)
    assert resolved.interval.indices.tolist() == [0, 1, 3]
    assert resolved.interval.sample_count == 3
    assert resolved.curve_ids == ("curve-c1", "curve-rop")


def test_current_and_selection_ranges_come_only_from_context() -> None:
    dataset = make_dataset()
    current = resolve_report_definition(
        dataset,
        definition(ReportIntervalSelection(ReportIntervalMode.CURRENT)),
        context=ReportIntervalContext(current_range=(1001.0, 1004.0)),
    )
    selected = resolve_report_definition(
        dataset,
        definition(ReportIntervalSelection(ReportIntervalMode.SELECTION)),
        context=ReportIntervalContext(selection_range=(1000.0, 1001.0)),
    )

    assert current.interval.indices.tolist() == [1, 3, 4]
    assert selected.interval.indices.tolist() == [0, 1]


def test_selection_mode_without_selection_is_rejected() -> None:
    with pytest.raises(ReportDefinitionError, match="selection"):
        resolve_report_definition(
            make_dataset(),
            definition(ReportIntervalSelection(ReportIntervalMode.SELECTION)),
        )


def test_missing_curve_and_wrong_dataset_are_rejected() -> None:
    dataset = make_dataset()
    missing = ReportDefinition(
        "report-2",
        "Gas",
        ReportProfile.GAS,
        dataset.dataset_id,
        dataset.active_index_id or "",
        ReportIntervalSelection(ReportIntervalMode.FULL),
        curve_ids=("missing",),
    )
    with pytest.raises(ReportDefinitionError, match="Каналы"):
        resolve_report_definition(dataset, missing)

    wrong = ReportDefinition(
        "report-3",
        "Gas",
        ReportProfile.GAS,
        "other",
        dataset.active_index_id or "",
        ReportIntervalSelection(ReportIntervalMode.FULL),
    )
    with pytest.raises(ReportDefinitionError, match="другому dataset"):
        resolve_report_definition(dataset, wrong)


def test_datetime_interval_uses_same_resolution_contract() -> None:
    dataset = make_dataset()
    time_index = DatasetIndex(
        "time-index",
        "DATETIME",
        IndexType.DATETIME,
        IndexRole.TIME,
        "UTC",
        np.array(
            [
                "2026-07-23T10:00:00",
                "2026-07-23T10:01:00",
                "NaT",
                "2026-07-23T10:03:00",
                "2026-07-23T10:04:00",
            ],
            dtype="datetime64[s]",
        ),
    )
    dataset.add_index(time_index)
    item = ReportDefinition(
        "report-time",
        "Time report",
        ReportProfile.DRILLING,
        dataset.dataset_id,
        time_index.index_id,
        ReportIntervalSelection(
            ReportIntervalMode.CUSTOM,
            "2026-07-23T10:00:30",
            "2026-07-23T10:03:30",
        ),
    )

    resolved = resolve_report_definition(dataset, item)

    assert resolved.interval.indices.tolist() == [1, 3]
    assert resolved.interval.start == "2026-07-23T10:00:30.000000000"
    assert resolved.interval.end == "2026-07-23T10:03:30.000000000"


def test_definition_payload_roundtrip_preserves_digest() -> None:
    original = definition(ReportIntervalSelection(ReportIntervalMode.FULL))

    restored = ReportDefinition.from_payload(original.payload())

    assert restored == original
    assert restored.content_sha256 == original.content_sha256


def test_definition_payload_rejects_non_object_section() -> None:
    payload = definition(ReportIntervalSelection(ReportIntervalMode.FULL)).payload()
    payload["sections"] = ["curves"]

    with pytest.raises(ValueError, match="sections"):
        ReportDefinition.from_payload(payload)
