import numpy as np

from geoworkbench.domain.models import (
    Dataset,
    DatasetIndex,
    DatasetKind,
    DepthDomain,
    IndexRole,
    IndexType,
    Well,
)
from geoworkbench.domain.operational_events import (
    DrillingEventPayload,
    GasEventPayload,
    OperationalEvent,
    OperationalEventKind,
    ShowEventPayload,
)
from geoworkbench.services.operational_event_report import resolve_operational_event_report
from geoworkbench.services.report_definition import (
    ReportDefinition,
    ReportIntervalMode,
    ReportIntervalSelection,
    ReportProfile,
    ReportSectionDefinition,
    ReportSectionKind,
    resolve_report_definition,
)


def make_depth_dataset() -> Dataset:
    return Dataset(
        dataset_id="dataset-1",
        name="Depth",
        kind=DatasetKind.GTI,
        depth_domain=DepthDomain.MD,
        depth=np.array([100.0, 101.0, 102.0, 103.0]),
    )


def test_event_report_reuses_exact_resolved_depth_interval() -> None:
    dataset = make_depth_dataset()
    well = Well("well-1", "Well 1", datasets={dataset.dataset_id: dataset})
    well.operational_events = {
        "drill": OperationalEvent(
            "drill",
            well.well_id,
            OperationalEventKind.DRILLING,
            DrillingEventPayload(activity="drilling"),
            depth_m=101.0,
        ),
        "gas": OperationalEvent(
            "gas",
            well.well_id,
            OperationalEventKind.GAS,
            GasEventPayload(total_gas_percent=2.0),
            depth_m=102.0,
        ),
        "show": OperationalEvent(
            "show",
            well.well_id,
            OperationalEventKind.SHOW,
            ShowEventPayload("oil"),
            depth_m=103.0,
        ),
    }
    definition = ReportDefinition(
        definition_id="report-1",
        name="Events",
        profile=ReportProfile.EVENTS,
        dataset_id=dataset.dataset_id,
        index_id=dataset.active_index_id or "",
        interval=ReportIntervalSelection(ReportIntervalMode.CUSTOM, 101.0, 102.0),
        sections=(
            ReportSectionDefinition(
                ReportSectionKind.EVENTS,
                options=(("event_kinds", "drilling,gas"),),
            ),
        ),
    )

    resolved = resolve_report_definition(dataset, definition)
    event_report = resolve_operational_event_report(well, dataset, resolved)

    assert event_report.start == resolved.interval.start == 101.0
    assert event_report.end == resolved.interval.end == 102.0
    assert event_report.event_ids == ("drill", "gas")


def test_event_report_maps_datetime_index_without_recalculating_rows() -> None:
    dataset = make_depth_dataset()
    dataset.add_index(
        DatasetIndex(
            index_id="datetime",
            mnemonic="DATE_TIME",
            index_type=IndexType.DATETIME,
            role=IndexRole.TIME,
            unit=None,
            values=np.array(
                [
                    "2026-07-23T05:00:00",
                    "2026-07-23T05:01:00",
                    "2026-07-23T05:02:00",
                    "2026-07-23T05:03:00",
                ],
                dtype="datetime64[ns]",
            ),
        ),
        make_active=True,
    )
    well = Well("well-1", "Well 1", datasets={dataset.dataset_id: dataset})
    well.operational_events["gas"] = OperationalEvent(
        "gas",
        well.well_id,
        OperationalEventKind.GAS,
        GasEventPayload(total_gas_percent=2.0),
        measured_at="2026-07-23T10:02:00+05:00",
    )
    definition = ReportDefinition(
        definition_id="report-2",
        name="Timed events",
        profile=ReportProfile.EVENTS,
        dataset_id=dataset.dataset_id,
        index_id="datetime",
        interval=ReportIntervalSelection(
            ReportIntervalMode.CUSTOM,
            "2026-07-23T05:01:00",
            "2026-07-23T05:02:00",
        ),
        sections=(ReportSectionDefinition(ReportSectionKind.EVENTS),),
    )

    resolved = resolve_report_definition(dataset, definition)
    event_report = resolve_operational_event_report(well, dataset, resolved)

    assert resolved.interval.indices.tolist() == [1, 2]
    assert event_report.event_ids == ("gas",)
    assert event_report.records[0].index_value == "2026-07-23T05:02:00.000000"
