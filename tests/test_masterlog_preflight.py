import numpy as np

from geoworkbench.domain.models import (
    CanvasObject,
    Dataset,
    DatasetIndex,
    DatasetKind,
    DepthDomain,
    IndexRole,
    IndexType,
    MasterlogColumnTemplate,
    MasterlogHeaderElement,
    MasterlogTemplate,
)
from geoworkbench.project.session import ProjectSession
from geoworkbench.printing.masterlog_output import MasterlogOutputSettings
from geoworkbench.printing.masterlog_preflight import (
    PreflightSeverity,
    analyze_masterlog_output,
)


def make_session() -> ProjectSession:
    dataset = Dataset(
        "dataset-1",
        "Log",
        DatasetKind.GTI,
        DepthDomain.MD,
        np.linspace(100.0, 300.0, 201),
    )
    dataset.upsert_curve("TG", np.linspace(1.0, 100.0, 201))
    session = ProjectSession()
    session.add_dataset(dataset, "Well")
    return session


def test_masterlog_preflight_reports_warnings_errors_and_page_count() -> None:
    session = make_session()
    gas_column = MasterlogColumnTemplate(
        "gas",
        "Gas",
        "curves",
        80.0,
        ["TG", "C1"],
        x_scale="logarithmic",
        x_min=1.0,
        x_max=100.0,
    )
    gas_column.x_min = -1.0
    template = MasterlogTemplate(
        "standard",
        "Standard",
        page_format="A4",
        header_elements=[
            MasterlogHeaderElement(
                "logo", "image", 205.0, 5.0, 20.0, 20.0, {"asset_ref": "missing"}
            )
        ],
        columns=[gas_column],
    )

    report = analyze_masterlog_output(template, session, MasterlogOutputSettings(100.0, 300.0))

    assert report.page_count == 2
    assert {issue.code for issue in report.errors} == {"invalid_log_range"}
    assert {issue.code for issue in report.warnings} == {
        "header_overflow",
        "missing_asset",
        "missing_curve",
    }
    assert all(issue.severity is PreflightSeverity.WARNING for issue in report.warnings)


def test_masterlog_preflight_blocks_empty_template() -> None:
    report = analyze_masterlog_output(
        MasterlogTemplate("empty", "Empty"),
        make_session(),
        MasterlogOutputSettings(100.0, 200.0),
    )
    assert [issue.code for issue in report.errors] == ["no_columns"]


def test_masterlog_preflight_accepts_saved_vendor_curve_mapping() -> None:
    session = make_session()
    dataset = session.current_dataset
    assert dataset is not None
    vendor = dataset.upsert_curve("VENDOR_METHANE", np.linspace(1.0, 2.0, 201))
    template = MasterlogTemplate(
        "mapped",
        "Mapped",
        columns=[MasterlogColumnTemplate("gas", "Gas", "curves", 40.0, ["C1"])],
        properties={
            "dataset_curve_bindings": {dataset.dataset_id: {"C1": vendor.metadata.curve_id}}
        },
    )

    report = analyze_masterlog_output(template, session, MasterlogOutputSettings(100.0, 300.0))

    assert not any(issue.code == "missing_curve" for issue in report.issues)


def test_masterlog_preflight_reports_broken_depth_symbol_references() -> None:
    session = make_session()
    template = MasterlogTemplate(
        "standard",
        "Standard",
        columns=[MasterlogColumnTemplate("gas", "Gas", "curves", 40.0)],
    )
    assert session.current_well is not None
    session.current_well.canvas_objects.append(
        CanvasObject(
            "show",
            "masterlog_symbol",
            "depth",
            0.0,
            150.0,
            8.0,
            8.0,
            top_depth=150.0,
            track_id="removed-column",
            properties={"template_id": "standard", "asset_ref": "missing"},
        )
    )

    report = analyze_masterlog_output(template, session, MasterlogOutputSettings(100.0, 200.0))

    assert {issue.code for issue in report.warnings} == {
        "missing_asset",
        "missing_symbol_column",
    }


def test_masterlog_preflight_reports_invalid_symbol_interval() -> None:
    session = make_session()
    template = MasterlogTemplate(
        "standard",
        "Standard",
        columns=[MasterlogColumnTemplate("gas", "Gas", "curves", 40.0)],
    )
    assert session.current_well is not None
    session.current_well.canvas_objects.append(
        CanvasObject(
            "zone",
            "masterlog_symbol",
            "interval",
            0.0,
            180.0,
            8.0,
            8.0,
            top_depth=180.0,
            bottom_depth=120.0,
            track_id="gas",
            properties={"template_id": "standard", "asset_ref": "missing"},
        )
    )

    report = analyze_masterlog_output(template, session, MasterlogOutputSettings(100.0, 200.0))

    assert {issue.code for issue in report.warnings} == {
        "missing_asset",
        "invalid_symbol_interval",
    }


def test_masterlog_preflight_reports_invalid_symbol_parameter() -> None:
    session = make_session()
    template = MasterlogTemplate(
        "standard",
        "Standard",
        columns=[MasterlogColumnTemplate("gas", "Gas", "curves", 40.0, ["TG"])],
    )
    assert session.current_well is not None
    session.current_well.canvas_objects.append(
        CanvasObject(
            "parameter",
            "masterlog_symbol",
            "parameter",
            0.0,
            150.0,
            8.0,
            8.0,
            top_depth=150.0,
            bottom_depth=150.0,
            parameter_mnemonic="ROP",
            track_id="gas",
            properties={"template_id": "standard", "asset_ref": "missing"},
        )
    )

    report = analyze_masterlog_output(template, session, MasterlogOutputSettings(100.0, 200.0))

    assert {issue.code for issue in report.warnings} == {
        "missing_asset",
        "invalid_symbol_parameter",
    }


def test_masterlog_preflight_reports_stale_time_depth_mapping() -> None:
    session = make_session()
    assert session.current_dataset is not None
    session.current_dataset.add_index(
        DatasetIndex(
            "time",
            "TIME",
            IndexType.RELATIVE_TIME,
            IndexRole.TIME,
            "s",
            np.linspace(0.0, 200.0, 201),
        )
    )
    template = MasterlogTemplate(
        "standard",
        "Standard",
        columns=[MasterlogColumnTemplate("gas", "Gas", "curves", 40.0, ["TG"])],
    )
    assert session.current_well is not None
    session.current_well.canvas_objects.append(
        CanvasObject(
            "time",
            "masterlog_symbol",
            "time",
            0.0,
            999.0,
            8.0,
            8.0,
            top_depth=999.0,
            bottom_depth=999.0,
            time_value="50",
            track_id="gas",
            properties={"template_id": "standard", "asset_ref": "missing"},
        )
    )

    report = analyze_masterlog_output(template, session, MasterlogOutputSettings(100.0, 200.0))

    assert {issue.code for issue in report.warnings} == {
        "missing_asset",
        "invalid_symbol_time",
    }


def test_masterlog_preflight_accepts_optional_blank_logo_placeholder() -> None:
    session = make_session()
    template = MasterlogTemplate(
        "optional-logo",
        "Optional logo",
        header_elements=[
            MasterlogHeaderElement(
                "logo",
                "image",
                5.0,
                5.0,
                30.0,
                15.0,
                {"optional": True, "placeholder_text_ru": "Загрузить логотип"},
            )
        ],
        columns=[MasterlogColumnTemplate("depth", "Depth", "depth", 20.0)],
    )

    report = analyze_masterlog_output(
        template, session, MasterlogOutputSettings(100.0, 200.0)
    )

    assert not any(issue.code == "missing_asset" for issue in report.issues)
