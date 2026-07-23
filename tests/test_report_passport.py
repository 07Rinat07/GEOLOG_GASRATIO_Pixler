from __future__ import annotations

import json
from dataclasses import replace
from pathlib import Path

import numpy as np
import pytest

from geoworkbench.domain.models import (
    CurveData,
    CurveMetadata,
    Dataset,
    DatasetKind,
    DepthDomain,
    Project,
    Well,
)
from geoworkbench.project.session import ProjectSession
from geoworkbench.services.report_passport import (
    ReportKind,
    ReportPassportBuilder,
    ReportPassportError,
    ReportPassportRequest,
    ReportRenderSettings,
    load_report_passport,
    passport_sidecar_path,
    write_report_passport,
)


def make_session() -> ProjectSession:
    dataset = Dataset(
        dataset_id="dataset-1",
        name="Well A LAS",
        kind=DatasetKind.GTI,
        depth_domain=DepthDomain.MD,
        depth=np.array([1000.0, 1001.0, 1002.0]),
        headers={"WELL": "Well A"},
    )
    source = CurveData(
        CurveMetadata(
            "curve-c1",
            "C1_RAW",
            "C1",
            "ppm",
            "Methane",
            dataset.dataset_id,
            provenance="source",
        ),
        np.array([10.0, np.nan, 30.0]),
    )
    calculated = CurveData(
        CurveMetadata(
            "curve-dexp",
            "DEXP",
            "DEXP",
            "dimensionless",
            "d-exponent",
            dataset.dataset_id,
            provenance="calculation:dexp.jorden_shirley:1.0.0",
        ),
        np.array([1.0, 1.1, 1.2]),
    )
    dataset.curves = {source.metadata.curve_id: source, calculated.metadata.curve_id: calculated}
    well = Well("well-1", "Well A", {dataset.dataset_id: dataset})
    project = Project("project-1", "Passport project", {well.well_id: well})
    return ProjectSession(project, well.well_id, dataset.dataset_id)


def request(*, curves: tuple[str, ...] | None = None) -> ReportPassportRequest:
    return ReportPassportRequest(
        ReportKind.VIEW,
        "Gas report",
        "ru",
        ReportRenderSettings(
            renderer="document-renderer:1",
            output_format="pdf",
            page_format="a4",
            orientation="portrait",
            dpi=300,
            margins_mm=(10.0, 10.0, 10.0, 10.0),
        ),
        interval=(1000.0, 1002.0),
        curve_mnemonics=curves,
    )


def test_report_passport_is_deterministic_and_self_verifying() -> None:
    session = make_session()
    builder = ReportPassportBuilder()

    first = builder.build(session, request())
    second = builder.build(session, request())

    assert first == second
    assert first.verify()
    assert first.passport_sha256 == second.passport_sha256
    assert first.dataset_sha256 == second.dataset_sha256
    assert first.interval.start == 1000.0
    assert {item.canonical_mnemonic for item in first.channels} == {"C1", "DEXP"}
    assert first.form.form_kind == "view"
    assert first.sources[-1].kind == "dataset-snapshot"


def test_report_passport_changes_when_report_data_changes() -> None:
    session = make_session()
    builder = ReportPassportBuilder()
    before = builder.build(session, request())

    session.current_dataset.curves["curve-c1"].values[0] = 11.0  # type: ignore[union-attr]
    after = builder.build(session, request())

    assert before.dataset_sha256 != after.dataset_sha256
    assert before.passport_sha256 != after.passport_sha256


def test_report_passport_only_includes_selected_channels_and_formula_versions() -> None:
    passport = ReportPassportBuilder().build(make_session(), request(curves=("DEXP",)))

    assert [item.curve_id for item in passport.channels] == ["curve-dexp"]
    assert len(passport.formulas) == 1
    formula = passport.formulas[0]
    assert formula.formula_id == "dexp.jorden_shirley"
    assert formula.version == "1.0.0"
    assert formula.expression_sha256 is not None


def test_report_passport_sidecar_roundtrip_and_tamper_detection(tmp_path) -> None:
    passport = ReportPassportBuilder().build(make_session(), request())
    output = tmp_path / "report.pdf"
    output.write_bytes(b"%PDF")

    sidecar = write_report_passport(passport, output)

    assert sidecar == passport_sidecar_path(output)
    assert load_report_passport(sidecar)["passport_sha256"] == passport.passport_sha256
    with pytest.raises(FileExistsError):
        write_report_passport(passport, output)

    payload = json.loads(sidecar.read_text(encoding="utf-8"))
    payload["report_name"] = "tampered"
    sidecar.write_text(json.dumps(payload), encoding="utf-8")
    with pytest.raises(ReportPassportError, match="SHA-256"):
        load_report_passport(sidecar)


def test_writer_rejects_modified_passport_digest(tmp_path) -> None:
    passport = ReportPassportBuilder().build(make_session(), request())
    invalid = replace(passport, report_name="Changed after signing")

    with pytest.raises(ReportPassportError, match="SHA-256"):
        write_report_passport(invalid, tmp_path / "report.pdf")


def test_report_passport_hashes_only_samples_inside_exact_interval() -> None:
    session = make_session()
    builder = ReportPassportBuilder()
    scoped_request = replace(request(), interval=(1000.0, 1001.0))

    before = builder.build(session, scoped_request)
    dataset = session.current_dataset
    assert dataset is not None
    dataset.curves["curve-c1"].values[2] = 999.0
    outside_change = builder.build(session, scoped_request)

    assert before.interval.sample_count == 2
    assert before.dataset_sha256 == outside_change.dataset_sha256
    assert before.passport_sha256 == outside_change.passport_sha256
    dataset.curves["curve-c1"].values[1] = 22.0
    inside_change = builder.build(session, scoped_request)
    assert inside_change.dataset_sha256 != before.dataset_sha256


def test_report_passport_captures_complete_semantic_binding() -> None:
    from geoworkbench.services.semantic_channels import SemanticChannelBinding
    from geoworkbench.services.uom_dictionary import QuantityClass

    session = make_session()
    dataset = session.current_dataset
    assert dataset is not None
    curve = dataset.curves["curve-c1"]
    binding = SemanticChannelBinding(
        canonical_kind="gas.c1",
        canonical_mnemonic="C1",
        quantity_class=QuantityClass.VOLUME_FRACTION,
        canonical_uom="ppm",
        source_uom="PPM",
        aliases=("C1", "CH4"),
        sensor_id="sensor-c1",
        source="Sensors catalog",
        family="gas",
        category="chromatography",
        source_mnemonic="C1_RAW",
        confidence=0.98,
        matched_by="alias",
        evidence=("alias:C1_RAW", "uom:ppm"),
    )
    curve.metadata = replace(curve.metadata, semantic=binding)

    passport = ReportPassportBuilder().build(session, request(curves=("C1",)))
    channel = passport.channels[0]

    assert channel.canonical_kind == "gas.c1"
    assert channel.quantity_class == "volume_fraction"
    assert channel.sensor_id == "sensor-c1"
    assert channel.semantic_source == "Sensors catalog"
    assert channel.confidence == 0.98
    assert channel.matched_by == "alias"
    assert channel.aliases == ("C1", "CH4")
    assert channel.evidence == ("alias:C1_RAW", "uom:ppm")


def test_report_passport_uses_stored_import_source_without_absolute_path() -> None:
    from hashlib import sha256

    from geoworkbench.data.las_import_report import LasImportReport, LasSourceSnapshot
    from geoworkbench.services.depth_axis import analyze_depth_axis

    session = make_session()
    source_bytes = b"~Version\nVERS. 2.0\n"
    session.import_reports["dataset-1"] = LasImportReport(
        source=LasSourceSnapshot(
            path=Path("/private/operator/run-42/input.las"),
            size_bytes=len(source_bytes),
            sha256=sha256(source_bytes).hexdigest(),
            encoding="ascii",
            newline_style="lf",
            section_names=("Version",),
            las_version="2.0",
            wrap="NO",
            null_value=-999.25,
        ),
        depth_axis=analyze_depth_axis(np.array([1000.0, 1001.0, 1002.0])),
        issues=(),
    )

    passport = ReportPassportBuilder().build(session, request())
    source = next(item for item in passport.sources if item.kind == "import-source")

    assert source.name == "input.las"
    assert source.capture == "stored-at-import"
    assert "/private/operator" not in passport.canonical_json()


def test_report_passport_marks_external_source_captured_at_report_time(tmp_path) -> None:
    session = make_session()
    dataset = session.current_dataset
    assert dataset is not None
    source = tmp_path / "source.csv"
    source.write_text("DEPTH,C1\n1000,10\n", encoding="utf-8")
    dataset.source_path = source

    passport = ReportPassportBuilder().build(session, request())
    external = next(item for item in passport.sources if item.kind == "external-source")

    assert external.name == "source.csv"
    assert external.capture == "captured-at-report-time"
    assert any(item.startswith("source-fingerprint-captured-at-report-time") for item in passport.warnings)


def test_report_form_revision_is_content_addressed() -> None:
    from geoworkbench.services.report_passport import tablet_layout_form_snapshot
    from geoworkbench.tablet.models import TabletLayout

    first = tablet_layout_form_snapshot(
        TabletLayout(visible_depth_top=1000.0, visible_depth_bottom=1002.0),
        dataset_id="dataset-1",
        name="View",
    )
    second = tablet_layout_form_snapshot(
        TabletLayout(visible_depth_top=1001.0, visible_depth_bottom=1002.0),
        dataset_id="dataset-1",
        name="View",
    )

    assert first.revision.startswith("schema:14/content:")
    assert first.definition_sha256 != second.definition_sha256
    assert first.revision != second.revision


def test_report_passport_warns_about_missing_requested_curve() -> None:
    passport = ReportPassportBuilder().build(
        make_session(), request(curves=("C1", "NOT_PRESENT"))
    )

    assert [item.curve_id for item in passport.channels] == ["curve-c1"]
    assert "curve-not-found:NOT_PRESENT" in passport.warnings


def test_well_level_artifact_passport_does_not_require_current_dataset() -> None:
    from geoworkbench.services.report_passport import (
        depth_interval_snapshot,
        report_definition_snapshot,
    )

    session = make_session()
    session.current_dataset_id = None
    payload = {
        "well": "Well A",
        "entries": [
            {"top_depth": 1000.0, "bottom_depth": 1001.0, "interpretation": "Gas show"}
        ],
    }
    artifact_request = ReportPassportRequest(
        ReportKind.INTERPRETATION,
        "Interpretation report",
        "en",
        ReportRenderSettings(
            renderer="interpretation-report:1",
            output_format="pdf",
            page_format="a4",
            orientation="portrait",
            dpi=300,
            margins_mm=(14.0, 14.0, 14.0, 14.0),
        ),
        form=report_definition_snapshot(
            "interpretation-report", "Interpretation report", {"columns": 4}
        ),
    )

    passport = ReportPassportBuilder().build_artifact(
        session,
        artifact_request,
        artifact_id="well-1:interpretation",
        artifact_name="Well A interpretation",
        payload=payload,
        interval=depth_interval_snapshot(((1000.0, 1001.0),), unit="m"),
    )

    assert passport.verify()
    assert passport.dataset_id == "well-1:interpretation"
    assert passport.interval is not None
    assert passport.interval.sample_count == 1
    assert passport.channels == ()
    assert passport.sources[0].kind == "report-data-snapshot"


def test_empty_well_level_artifact_has_no_fake_interval() -> None:
    session = make_session()
    session.current_dataset_id = None
    artifact_request = ReportPassportRequest(
        ReportKind.INTERPRETATION,
        "Empty interpretation report",
        "ru",
        ReportRenderSettings("interpretation-report:1", "pdf"),
    )

    passport = ReportPassportBuilder().build_artifact(
        session,
        artifact_request,
        artifact_id="well-1:empty-interpretation",
        artifact_name="Empty interpretation",
        payload={"entries": []},
    )

    assert passport.interval is None
    assert passport.verify()
