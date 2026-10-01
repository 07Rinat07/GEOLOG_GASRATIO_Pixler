from __future__ import annotations

from dataclasses import FrozenInstanceError
from pathlib import Path
from types import SimpleNamespace

import numpy as np
import pytest
from PySide6.QtGui import QPageLayout

from geoworkbench.domain.models import (
    CurveData,
    CurveMetadata,
    CuttingsComponent,
    CuttingsSample,
    Dataset,
    DatasetIndex,
    DatasetKind,
    DepthDomain,
    IndexRole,
    IndexType,
    LithologyInterval,
    Project,
    Well,
)
from geoworkbench.printing.hydrocarbon_interpretation_report import (
    export_hydrocarbon_interpretation_pdf_with_passport,
)
from geoworkbench.printing.hydrocarbon_interpretation_report_identity import (
    InterpretationReportIdentity,
)
from geoworkbench.printing.hydrocarbon_interpretation_geology_settings import (
    GeologyTrackVisibility,
    InterpretationGeologyTrackSettings,
)
from geoworkbench.project.session import ProjectSession
from geoworkbench.services.hydrocarbon_interpretation import (
    HydrocarbonInterpretationReport,
    InterpretationMethodStatus,
)
from geoworkbench.services.localization import AppLanguage
from geoworkbench.services.report_geology_snapshot import (
    build_report_geology_snapshot,
)
from geoworkbench.services.report_passport import (
    ReportKind,
    ReportPassportBuilder,
    ReportPassportRequest,
    ReportRenderSettings,
)


def _session() -> ProjectSession:
    dataset = Dataset(
        dataset_id="dataset-geo",
        name="Geology report dataset",
        kind=DatasetKind.GTI,
        depth_domain=DepthDomain.MD,
        depth=np.array([1000.0, 1005.0, 1010.0, 1015.0]),
        headers={"WELL": "Well Geo"},
    )
    curve = CurveData(
        CurveMetadata(
            "curve-c1",
            "C1",
            "C1",
            "%",
            "Methane",
            dataset.dataset_id,
            provenance="source",
        ),
        np.array([1.0, 2.0, 3.0, 4.0]),
    )
    dataset.curves = {curve.metadata.curve_id: curve}
    well = Well("well-geo", "Well Geo", {dataset.dataset_id: dataset})
    well.lithology.extend(
        [
            LithologyInterval(
                "lith-in",
                1000.0,
                1008.0,
                "sandstone",
                "Sandstone",
                {"ru": "Песчаник"},
            ),
            LithologyInterval(
                "lith-out",
                1020.0,
                1030.0,
                "limestone",
                "Outside",
            ),
        ]
    )
    well.cuttings.extend(
        [
            CuttingsSample(
                "sample-in",
                1004.0,
                1009.0,
                [
                    CuttingsComponent("sandstone", 70.0),
                    CuttingsComponent("clay", 30.0),
                ],
                lba_group=2,
                lba_type_id="oily",
                lba_intensity=3,
                lba_color="yellow",
                description="Mixed cuttings",
            ),
            CuttingsSample(
                "sample-out",
                1020.0,
                1025.0,
                [CuttingsComponent("limestone", 100.0)],
                lba_group=1,
            ),
        ]
    )
    project = Project("project-geo", "Geology report project", {well.well_id: well})
    return ProjectSession(project, well.well_id, dataset.dataset_id)


def _request(kind: ReportKind) -> ReportPassportRequest:
    return ReportPassportRequest(
        report_kind=kind,
        report_name="Gas interpretation",
        language="ru",
        render=ReportRenderSettings(
            renderer="interpretation-report:1",
            output_format="pdf",
        ),
        interval=(1000.0, 1010.0),
        curve_mnemonics=("C1",),
    )


def _report() -> HydrocarbonInterpretationReport:
    return HydrocarbonInterpretationReport(
        project_name="Geology report project",
        well_name="Well Geo",
        dataset_id="dataset-geo",
        dataset_name="Geology report dataset",
        generated_at="2026-10-01T00:00:00Z",
        depth_unit="m",
        threshold=3.0,
        primary_mnemonic="C1",
        baseline_median=None,
        robust_scale=None,
        methods=(
            InterpretationMethodStatus(
                method="gas",
                curve_mnemonics=("C1",),
                available_mnemonics=("C1",),
                source="source",
            ),
        ),
        candidates=(),
        manual_intervals=(),
        warnings=(),
    )


def _identity() -> InterpretationReportIdentity:
    return InterpretationReportIdentity(
        report_title="Gas interpretation",
        report_subtitle="",
        project_name="Geology report project",
        well_name="Well Geo",
        dataset_name="Geology report dataset",
        interval="1000–1010 m",
    )


def test_report_geology_snapshot_is_scoped_and_deeply_immutable() -> None:
    session = _session()

    snapshot = build_report_geology_snapshot(session, interval=(1000.0, 1010.0))

    assert snapshot.verify()
    assert snapshot.has_data
    assert [item.interval_id for item in snapshot.lithology] == ["lith-in"]
    assert [item.sample_id for item in snapshot.cuttings] == ["sample-in"]
    assert [item.lithotype_id for item in snapshot.lithotypes] == ["clay", "sandstone"]
    assert [item.percentage for item in snapshot.cuttings[0].components] == [70.0, 30.0]
    with pytest.raises(FrozenInstanceError):
        snapshot.cuttings[0].lba_color = "brown"  # type: ignore[misc]

    well = session.current_well
    assert well is not None
    well.cuttings[0].components[0].percentage = 55.0
    well.cuttings[0].lba_color = "brown"

    assert [item.percentage for item in snapshot.cuttings[0].components] == [70.0, 30.0]
    assert snapshot.cuttings[0].lba_color == "yellow"
    changed = build_report_geology_snapshot(session, interval=(1000.0, 1010.0))
    assert changed.geology_sha256 != snapshot.geology_sha256


def test_report_geology_snapshot_normalizes_reversed_depth_bounds() -> None:
    session = _session()
    before = build_report_geology_snapshot(session, interval=(1000.0, 1010.0))
    well = session.current_well
    assert well is not None

    well.lithology[0].top_depth, well.lithology[0].bottom_depth = (
        well.lithology[0].bottom_depth,
        well.lithology[0].top_depth,
    )
    well.cuttings[0].top_depth, well.cuttings[0].bottom_depth = (
        well.cuttings[0].bottom_depth,
        well.cuttings[0].top_depth,
    )
    after = build_report_geology_snapshot(session, interval=(1000.0, 1010.0))

    assert after.lithology[0].top_depth == 1000.0
    assert after.lithology[0].bottom_depth == 1008.0
    assert after.cuttings[0].top_depth == 1004.0
    assert after.cuttings[0].bottom_depth == 1009.0
    assert after.geology_sha256 == before.geology_sha256


def test_interpretation_passport_fingerprints_geology_without_changing_dataset() -> None:
    session = _session()
    builder = ReportPassportBuilder()

    before = builder.build(session, _request(ReportKind.INTERPRETATION))
    before_geology = next(item for item in before.sources if item.kind == "geology-snapshot")
    before_channel = before.channels[0]

    well = session.current_well
    assert well is not None
    well.cuttings[0].lba_intensity = 5
    well.cuttings[0].components[1].percentage = 35.0

    after = builder.build(session, _request(ReportKind.INTERPRETATION))
    after_geology = next(item for item in after.sources if item.kind == "geology-snapshot")
    after_channel = after.channels[0]

    assert before_geology.capture == "normalized-project-geology"
    assert len(before_geology.sha256) == 64
    assert before_geology.sha256 != after_geology.sha256
    assert before.dataset_sha256 == after.dataset_sha256
    assert before_channel.values_sha256 == after_channel.values_sha256
    assert before.passport_sha256 != after.passport_sha256


def test_non_interpretation_passport_does_not_acquire_geology_source() -> None:
    passport = ReportPassportBuilder().build(_session(), _request(ReportKind.VIEW))

    assert all(item.kind != "geology-snapshot" for item in passport.sources)


def test_time_index_interpretation_passport_does_not_claim_depth_geology() -> None:
    session = _session()
    dataset = session.current_dataset
    assert dataset is not None
    time_index = DatasetIndex(
        index_id="time-index",
        mnemonic="TIME",
        index_type=IndexType.RELATIVE_TIME,
        role=IndexRole.TIME,
        unit="s",
        values=np.array([0.0, 5.0, 10.0, 15.0]),
    )
    dataset.add_index(time_index, make_active=True)
    request = ReportPassportRequest(
        report_kind=ReportKind.INTERPRETATION,
        report_name="Time interpretation",
        language="ru",
        render=ReportRenderSettings("interpretation-report:1", "pdf"),
        interval=(0.0, 10.0),
        curve_mnemonics=("C1",),
    )

    passport = ReportPassportBuilder().build(session, request)

    assert passport.interval.role == "time"
    assert all(item.kind != "geology-snapshot" for item in passport.sources)


def test_production_pdf_export_builds_interpretation_passport_with_geology(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    session = _session()
    observed = {}

    def capture_transaction(output, producer, passport, *, overwrite=False):
        observed["output"] = Path(output)
        observed["passport"] = passport
        observed["overwrite"] = overwrite
        return SimpleNamespace(primary_path=Path(output))

    monkeypatch.setattr(
        "geoworkbench.printing.hydrocarbon_interpretation_report."
        "execute_report_output_transaction",
        capture_transaction,
    )

    result = export_hydrocarbon_interpretation_pdf_with_passport(
        session,
        _report(),
        tmp_path / "interpretation.pdf",
        language=AppLanguage.RU,
        include_chart=True,
        orientation=QPageLayout.Orientation.Landscape,
        identity=_identity(),
        geology_track_settings=InterpretationGeologyTrackSettings(
            cuttings=GeologyTrackVisibility.SHOW,
            lba=GeologyTrackVisibility.HIDE,
        ),
    )

    passport = observed["passport"]
    geology = next(item for item in passport.sources if item.kind == "geology-snapshot")
    assert result.primary_path == tmp_path / "interpretation.pdf"
    assert passport.report_kind is ReportKind.INTERPRETATION
    assert passport.interval.role == "depth"
    assert passport.interval.start == 1000.0
    assert passport.interval.end == 1010.0
    assert geology.capture == "normalized-project-geology"
    assert geology.sha256 == build_report_geology_snapshot(
        session,
        interval=(1000.0, 1010.0),
    ).geology_sha256
    assert [channel.original_mnemonic for channel in passport.channels] == ["C1"]
    assert dict(passport.render.options) == {
        "geology_cuttings": "show",
        "geology_lba": "hide",
    }
    assert observed["overwrite"] is False
