from __future__ import annotations

import zipfile

import numpy as np
import pytest

from geoworkbench.brand import APPLICATION_DISPLAY_NAME
from geoworkbench.data.report_document_export import (
    MISSING_CELL,
    REPORT_DOCUMENT_SCHEMA_VERSION,
    UNAVAILABLE_CELL,
    ReportDocumentColumn,
    ReportDocumentExportError,
    _disambiguate_visible_columns,
    build_report_document_model,
    export_report_docx,
    export_report_html,
)
from geoworkbench.domain.models import (
    CurveData,
    CurveMetadata,
    Dataset,
    DatasetKind,
    DepthDomain,
)
from geoworkbench.services.localization import AppLanguage
from geoworkbench.services.report_definition import (
    ReportDefinition,
    ReportIntervalContext,
    ReportIntervalMode,
    ReportIntervalSelection,
    ReportProfile,
    resolve_report_definition,
)


def _resolved_report():
    dataset = Dataset(
        "dataset-1",
        "Well A",
        DatasetKind.GTI,
        DepthDomain.MD,
        np.array([100.0, 101.0, 102.0, 103.0]),
    )
    dataset.curves["c1"] = CurveData(
        CurveMetadata("c1", "C1", "C1", "ppm", "Methane", dataset.dataset_id),
        np.array([0.0, np.nan, 25.0, 30.0]),
    )
    definition = ReportDefinition(
        "selection:dataset-1",
        "Gas interval",
        ReportProfile.GAS,
        dataset.dataset_id,
        dataset.active_index_id or "",
        ReportIntervalSelection(ReportIntervalMode.SELECTION),
        language="en",
        curve_ids=("c1",),
        channel_mnemonics=("C1", "H2S"),
    )
    report = resolve_report_definition(
        dataset,
        definition,
        context=ReportIntervalContext(selection_range=(100.0, 102.0)),
        require_curves=True,
    )
    return dataset, report


def test_document_model_uses_resolved_indices_and_coverage_states() -> None:
    dataset, report = _resolved_report()

    model = build_report_document_model(dataset, report)

    assert model.schema_version == REPORT_DOCUMENT_SCHEMA_VERSION
    assert model.sample_count == 3
    assert [column.technical_name for column in model.columns] == ["DEPTH", "C1", "H2S"]
    assert [column.header for column in model.columns] == [
        "Depth [m]",
        "Methane [ppm]",
        "Hydrogen sulfide",
    ]
    assert model.rows[0] == ("100", "0", UNAVAILABLE_CELL)
    assert model.rows[1] == ("101", MISSING_CELL, UNAVAILABLE_CELL)
    assert model.rows[2] == ("102", "25", UNAVAILABLE_CELL)
    assert model.columns[1].coverage is not None
    assert model.columns[1].coverage.zero_count == 1
    assert model.columns[1].coverage.missing_count == 1
    assert model.columns[2].coverage is not None
    assert model.columns[2].coverage.unavailable_count == 3


@pytest.mark.parametrize(
    ("language", "gas_header", "unavailable_header"),
    [
        (AppLanguage.RU, "Содержание метана [ppm]", "Сероводород"),
        (AppLanguage.KK, "Метан [ppm]", "Күкіртсутек"),
        (AppLanguage.EN, "Methane [ppm]", "Hydrogen sulfide"),
    ],
)
def test_document_headers_are_localized_without_exposing_mnemonics(
    language: AppLanguage,
    gas_header: str,
    unavailable_header: str,
) -> None:
    dataset, report = _resolved_report()

    model = build_report_document_model(dataset, report, language=language)

    assert model.columns[1].technical_name == "C1"
    assert model.columns[2].technical_name == "H2S"
    assert model.columns[1].header == gas_header
    assert model.columns[2].header == unavailable_header
    assert "C1" not in model.columns[1].header
    assert "H2S" not in model.columns[2].header


def test_unavailable_unknown_channel_uses_localized_neutral_placeholder() -> None:
    dataset, _report = _resolved_report()
    definition = ReportDefinition(
        "selection:dataset-1:unknown",
        "Gas interval",
        ReportProfile.GAS,
        dataset.dataset_id,
        dataset.active_index_id or "",
        ReportIntervalSelection(ReportIntervalMode.SELECTION),
        language="en",
        curve_ids=("c1",),
        channel_mnemonics=("C1", "VENDOR_UNKNOWN_17"),
    )
    report = resolve_report_definition(
        dataset,
        definition,
        context=ReportIntervalContext(selection_range=(100.0, 102.0)),
        require_curves=True,
    )

    model = build_report_document_model(dataset, report, language=AppLanguage.EN)

    assert model.columns[2].technical_name == "VENDOR_UNKNOWN_17"
    assert model.columns[2].header == "Unresolved channel"
    assert "VENDOR_UNKNOWN_17" not in model.columns[2].header


def test_unavailable_known_channel_keeps_readable_physical_name() -> None:
    dataset, _report = _resolved_report()
    definition = ReportDefinition(
        "selection:dataset-1:total",
        "Gas interval",
        ReportProfile.GAS,
        dataset.dataset_id,
        dataset.active_index_id or "",
        ReportIntervalSelection(ReportIntervalMode.SELECTION),
        language="en",
        curve_ids=("c1",),
        channel_mnemonics=("C1", "TOTAL_GAS"),
    )
    report = resolve_report_definition(
        dataset,
        definition,
        context=ReportIntervalContext(selection_range=(100.0, 102.0)),
        require_curves=True,
    )

    model = build_report_document_model(dataset, report, language=AppLanguage.EN)

    assert model.columns[2].technical_name == "TOTAL_GAS"
    assert model.columns[2].header == "Total Gas"
    assert model.columns[2].availability is not None
    assert "TOTAL_GAS" not in model.columns[2].header


@pytest.mark.parametrize(
    ("mnemonic", "expected"),
    [
        ("TOTAL_GAS", "Total Gas"),
        ("FLOW_IN", "Flow In"),
        ("OPUS3", "OPUS-3"),
    ],
)
def test_available_curated_english_labels_are_not_masked(
    mnemonic: str,
    expected: str,
) -> None:
    dataset, _report = _resolved_report()
    dataset.curves["curated"] = CurveData(
        CurveMetadata(
            "curated",
            mnemonic,
            mnemonic,
            "",
            None,
            dataset.dataset_id,
        ),
        np.array([1.0, 2.0, 3.0, 4.0]),
    )
    definition = ReportDefinition(
        f"selection:dataset-1:curated:{mnemonic}",
        "Curated label report",
        ReportProfile.COMBINED,
        dataset.dataset_id,
        dataset.active_index_id or "",
        ReportIntervalSelection(ReportIntervalMode.SELECTION),
        language="en",
        curve_ids=("curated",),
    )
    report = resolve_report_definition(
        dataset,
        definition,
        context=ReportIntervalContext(selection_range=(100.0, 102.0)),
        require_curves=True,
    )

    model = build_report_document_model(dataset, report, language=AppLanguage.EN)

    assert model.columns[1].technical_name == mnemonic
    assert model.columns[1].header == expected


@pytest.mark.parametrize("mnemonic", ["MS_H2S", "BIT_DEPTH_STANDS"])
def test_unavailable_prettified_technical_names_are_masked(mnemonic: str) -> None:
    dataset, _report = _resolved_report()
    definition = ReportDefinition(
        f"selection:dataset-1:unavailable:{mnemonic}",
        "Unavailable technical label report",
        ReportProfile.COMBINED,
        dataset.dataset_id,
        dataset.active_index_id or "",
        ReportIntervalSelection(ReportIntervalMode.SELECTION),
        language="en",
        curve_ids=("c1",),
        channel_mnemonics=("C1", mnemonic),
    )
    report = resolve_report_definition(
        dataset,
        definition,
        context=ReportIntervalContext(selection_range=(100.0, 102.0)),
        require_curves=True,
    )

    model = build_report_document_model(dataset, report, language=AppLanguage.EN)

    assert model.columns[2].technical_name == mnemonic
    assert model.columns[2].header == "Unresolved channel"
    assert mnemonic not in model.columns[2].header


def test_duplicate_physical_headers_use_localized_source_ordinals() -> None:
    dataset, _report = _resolved_report()
    dataset.curves["c1-backup"] = CurveData(
        CurveMetadata(
            "c1-backup",
            "METHANE_BACKUP_SENSOR",
            "C1",
            "ppm",
            "Backup methane sensor",
            dataset.dataset_id,
        ),
        np.array([1.0, 2.0, 3.0, 4.0]),
    )
    definition = ReportDefinition(
        "selection:dataset-1:duplicate-c1",
        "Gas interval",
        ReportProfile.GAS,
        dataset.dataset_id,
        dataset.active_index_id or "",
        ReportIntervalSelection(ReportIntervalMode.SELECTION),
        language="en",
        curve_ids=("c1", "c1-backup"),
    )
    report = resolve_report_definition(
        dataset,
        definition,
        context=ReportIntervalContext(selection_range=(100.0, 102.0)),
        require_curves=True,
    )

    model = build_report_document_model(dataset, report, language=AppLanguage.EN)

    assert [column.technical_name for column in model.columns[1:]] == [
        "C1",
        "METHANE_BACKUP_SENSOR",
    ]
    assert [column.header for column in model.columns[1:]] == [
        "Methane (source 1) [ppm]",
        "Methane (source 2) [ppm]",
    ]
    assert all("C1" not in column.header for column in model.columns[1:])
    assert all("METHANE_BACKUP_SENSOR" not in column.header for column in model.columns[1:])


def test_generated_source_ordinals_skip_already_reserved_headers() -> None:
    columns = [
        ReportDocumentColumn("a", "Methane", "A", "ppm", None, None),
        ReportDocumentColumn("b", "Methane", "B", "ppm", None, None),
        ReportDocumentColumn(
            "c",
            "Methane (source 1)",
            "C",
            "ppm",
            None,
            None,
        ),
    ]

    result = _disambiguate_visible_columns(columns, source_label="source")

    assert [column.header for column in result] == [
        "Methane (source 2) [ppm]",
        "Methane (source 3) [ppm]",
        "Methane (source 1) [ppm]",
    ]


def test_generic_index_keeps_nontechnical_visible_identity() -> None:
    from geoworkbench.domain.models import DatasetIndex, IndexRole, IndexType

    dataset, _report = _resolved_report()
    dataset.add_index(
        DatasetIndex(
            "generic-index",
            "CUSTOM_AXIS",
            IndexType.GENERIC,
            IndexRole.GENERIC,
            "arb",
            np.array([10.0, 20.0, 30.0, 40.0]),
        ),
        make_active=True,
    )
    definition = ReportDefinition(
        "generic:dataset-1",
        "Generic index report",
        ReportProfile.GAS,
        dataset.dataset_id,
        "generic-index",
        ReportIntervalSelection(ReportIntervalMode.CUSTOM, 10.0, 30.0),
        language="en",
        curve_ids=("c1",),
    )
    report = resolve_report_definition(dataset, definition, require_curves=True)

    model = build_report_document_model(dataset, report, language=AppLanguage.EN)

    assert model.columns[0].technical_name == "CUSTOM_AXIS"
    assert model.columns[0].header == "Index 2 [arb]"
    assert "CUSTOM_AXIS" not in model.columns[0].header


def test_available_unknown_curve_uses_neutral_header_but_keeps_audit_name() -> None:
    dataset, _report = _resolved_report()
    dataset.curves["unknown"] = CurveData(
        CurveMetadata(
            "unknown",
            "VENDOR_UNKNOWN_17",
            "VENDOR_UNKNOWN_17",
            "ppm",
            None,
            dataset.dataset_id,
        ),
        np.array([1.0, 2.0, 3.0, 4.0]),
    )
    definition = ReportDefinition(
        "selection:dataset-1:unknown-available",
        "Unknown curve report",
        ReportProfile.GAS,
        dataset.dataset_id,
        dataset.active_index_id or "",
        ReportIntervalSelection(ReportIntervalMode.SELECTION),
        language="en",
        curve_ids=("unknown",),
    )
    report = resolve_report_definition(
        dataset,
        definition,
        context=ReportIntervalContext(selection_range=(100.0, 102.0)),
        require_curves=True,
    )

    model = build_report_document_model(dataset, report, language=AppLanguage.EN)

    assert model.columns[1].technical_name == "VENDOR_UNKNOWN_17"
    assert model.columns[1].header == "Unresolved channel [ppm]"
    assert "VENDOR_UNKNOWN_17" not in model.columns[1].header


def test_prettified_technical_fallback_is_masked_for_available_curve() -> None:
    dataset, _report = _resolved_report()
    dataset.curves["sensor-111"] = CurveData(
        CurveMetadata(
            "sensor-111",
            "SENSOR_111",
            "SENSOR_111",
            "psi",
            None,
            dataset.dataset_id,
        ),
        np.array([1.0, 2.0, 3.0, 4.0]),
    )
    definition = ReportDefinition(
        "selection:dataset-1:sensor-111",
        "Technical fallback report",
        ReportProfile.COMBINED,
        dataset.dataset_id,
        dataset.active_index_id or "",
        ReportIntervalSelection(ReportIntervalMode.SELECTION),
        language="en",
        curve_ids=("sensor-111",),
    )
    report = resolve_report_definition(
        dataset,
        definition,
        context=ReportIntervalContext(selection_range=(100.0, 102.0)),
        require_curves=True,
    )

    model = build_report_document_model(dataset, report, language=AppLanguage.EN)

    assert model.columns[1].technical_name == "SENSOR_111"
    assert model.columns[1].header == "Unresolved channel [psi]"
    assert "Sensor 111" not in model.columns[1].header
    assert "SENSOR_111" not in model.columns[1].header


def test_index_curve_header_collision_is_disambiguated_without_mnemonics() -> None:
    dataset, _report = _resolved_report()
    dataset.curves["depth-like"] = CurveData(
        CurveMetadata(
            "depth-like",
            "VENDOR_DEPTH_COPY",
            "VENDOR_DEPTH_COPY",
            "",
            "Depth [m]",
            dataset.dataset_id,
        ),
        np.array([1.0, 2.0, 3.0, 4.0]),
    )
    definition = ReportDefinition(
        "selection:dataset-1:index-collision",
        "Index collision report",
        ReportProfile.COMBINED,
        dataset.dataset_id,
        dataset.active_index_id or "",
        ReportIntervalSelection(ReportIntervalMode.SELECTION),
        language="en",
        curve_ids=("depth-like",),
    )
    report = resolve_report_definition(
        dataset,
        definition,
        context=ReportIntervalContext(selection_range=(100.0, 102.0)),
        require_curves=True,
    )

    model = build_report_document_model(dataset, report, language=AppLanguage.EN)

    assert [column.header for column in model.columns] == [
        "Depth (source 1) [m]",
        "Depth [m] (source 2)",
    ]
    assert model.columns[1].technical_name == "VENDOR_DEPTH_COPY"
    assert all("VENDOR_DEPTH_COPY" not in column.header for column in model.columns)


def test_html_export_is_self_contained_and_explicit_about_coverage(tmp_path) -> None:
    dataset, report = _resolved_report()
    target = tmp_path / "report.html"

    export_report_html(dataset, target, report)

    text = target.read_text(encoding="utf-8")
    assert '<html lang="en">' in text
    assert "Gas interval" in text
    assert "Methane [ppm]" in text
    assert "Hydrogen sulfide" in text
    assert "Methane · C1" not in text
    assert "H2S" not in text
    assert 'data-state="zero">0</td>' in text
    assert 'data-state="missing">—</td>' in text
    assert 'data-state="unavailable">#N/A</td>' in text
    assert "ReportDefinition SHA-256" in text
    assert report.definition.content_sha256 in text
    assert "http://" not in text
    assert "https://" not in text
    assert "<script" not in text


def test_docx_export_is_valid_deterministic_openxml(tmp_path) -> None:
    dataset, report = _resolved_report()
    first = tmp_path / "first.docx"
    second = tmp_path / "second.docx"

    export_report_docx(dataset, first, report)
    export_report_docx(dataset, second, report)

    assert first.read_bytes() == second.read_bytes()
    with zipfile.ZipFile(first) as archive:
        assert archive.testzip() is None
        assert set(archive.namelist()) >= {
            "[Content_Types].xml",
            "_rels/.rels",
            "word/document.xml",
            "word/styles.xml",
            "docProps/core.xml",
        }
        document = archive.read("word/document.xml").decode("utf-8")
        core = archive.read("docProps/core.xml").decode("utf-8")
    assert "Gas interval" in document
    assert "Methane [ppm]" in document
    assert "Hydrogen sulfide" in document
    assert "Methane · C1" not in document
    assert "H2S" not in document
    assert "#N/A" in document
    assert "—" in document
    assert "0" in document
    assert report.definition.content_sha256 in document
    assert APPLICATION_DISPLAY_NAME in core


def test_document_export_validates_suffix_and_overwrite(tmp_path) -> None:
    dataset, report = _resolved_report()
    invalid = tmp_path / "report.pdf"
    with pytest.raises(ReportDocumentExportError, match="расширение"):
        export_report_docx(dataset, invalid, report)

    target = tmp_path / "report.html"
    export_report_html(dataset, target, report)
    with pytest.raises(FileExistsError):
        export_report_html(dataset, target, report)
    export_report_html(dataset, target, report, overwrite=True)


def test_document_export_supports_resolved_datetime_index(tmp_path) -> None:
    from geoworkbench.domain.models import DatasetIndex, IndexRole, IndexType

    dataset, _report = _resolved_report()
    dataset.add_index(
        DatasetIndex(
            "time-index",
            "DATETIME",
            IndexType.DATETIME,
            IndexRole.TIME,
            None,
            np.array(
                [
                    "2026-07-23T10:00:00.000",
                    "2026-07-23T10:00:01.250",
                    "2026-07-23T10:00:02.500",
                    "2026-07-23T10:00:03.750",
                ],
                dtype="datetime64[ns]",
            ),
            timezone="UTC",
        ),
        make_active=True,
    )
    definition = ReportDefinition(
        "time:dataset-1",
        "Time report",
        ReportProfile.GAS,
        dataset.dataset_id,
        "time-index",
        ReportIntervalSelection(
            ReportIntervalMode.CUSTOM,
            "2026-07-23T10:00:01.250",
            "2026-07-23T10:00:02.500",
        ),
        language="en",
        curve_ids=("c1",),
    )
    report = resolve_report_definition(dataset, definition, require_curves=True)

    target = export_report_html(dataset, tmp_path / "time.html", report)
    text = target.read_text(encoding="utf-8")

    assert report.interval.sample_count == 2
    assert "2026-07-23T10:00:01.250" in text
    assert "2026-07-23T10:00:02.500" in text
    assert "2026-07-23T10:00:00.000" not in text


def test_html_export_is_deterministic_for_same_model(tmp_path) -> None:
    dataset, report = _resolved_report()
    first = tmp_path / "first.html"
    second = tmp_path / "second.html"

    export_report_html(dataset, first, report)
    export_report_html(dataset, second, report)

    assert first.read_bytes() == second.read_bytes()
