"""Saved metre MD geology must never inherit a foreign coordinate system."""
from dataclasses import replace

import numpy as np
import pytest

from geoworkbench.domain.models import DatasetIndex, IndexRole, IndexType
from geoworkbench.printing.hydrocarbon_interpretation_geology import (
    geology_for_dataset, interpretation_geology_snapshot,
)
from geoworkbench.services.geology_depth_alignment import supports_saved_md_geology
from geoworkbench.services.interpretation_geology_interval_evidence import correlate_gas_interval_with_well_geology
from test_report_geology_snapshot import _session


@pytest.mark.parametrize(("kind", "role", "unit", "expected"), (
    (IndexType.MD, IndexRole.DEPTH, "m", True),
    (IndexType.MD, IndexRole.DEPTH, " Metres ", True),
    (IndexType.MD, IndexRole.DEPTH, "ft", False),
    (IndexType.MD, IndexRole.DEPTH, None, False),
    (IndexType.MD, IndexRole.DEPTH, "", False),
    (IndexType.TVD, IndexRole.DEPTH, "m", False),
    (IndexType.TVDSS, IndexRole.DEPTH, "m", False),
    (IndexType.RELATIVE_TIME, IndexRole.TIME, "s", False),
))
def test_snapshot_and_interval_table_use_same_verified_md_contract(kind, role, unit, expected):
    session = _session()
    dataset = session.current_dataset
    dataset.add_index(DatasetIndex("selected", "SELECTED", kind, role, unit, dataset.depth.copy()), make_active=True)
    source = dataset.depth.copy()
    samples = repr(session.current_well.cuttings)
    assert supports_saved_md_geology(dataset) is expected
    geology = interpretation_geology_snapshot(session)
    assert (geology is not None) is expected
    if expected:
        assert geology.dataset_id == dataset.dataset_id
        assert geology.depth_axis_id == "selected"
        assert geology_for_dataset(geology, dataset) is geology
        assert correlate_gas_interval_with_well_geology(session, top_depth=1002.0, bottom_depth=1010.0).intersections
    else:
        with pytest.raises(ValueError, match="explicit metre MD"):
            correlate_gas_interval_with_well_geology(session, top_depth=1002.0, bottom_depth=1010.0)
    np.testing.assert_array_equal(dataset.depth, source)
    assert repr(session.current_well.cuttings) == samples


@pytest.mark.parametrize("change", ("dataset", "axis", "unit", "tvd"))
def test_session_snapshot_cannot_be_reused_after_source_or_coordinate_change(change):
    session = _session()
    dataset = session.current_dataset
    snapshot = interpretation_geology_snapshot(session)
    assert snapshot is not None
    if change == "dataset":
        dataset.dataset_id = "other"
    elif change == "axis":
        dataset.add_index(replace(dataset.active_index, index_id="other"), make_active=True)
    elif change == "unit":
        dataset.active_index.unit = "ft"
    else:
        dataset.active_index.index_type = IndexType.TVD
    assert geology_for_dataset(snapshot, dataset) is None


def test_lag_correction_does_not_inherit_raw_md_geology_and_raw_projection_still_works():
    from test_interpretation_lag_axis_gas_context import _lagged_session
    from geoworkbench.domain.lag_correction import LagCorrectionAxisMode
    from geoworkbench.domain.models import CuttingsSample

    session, controller, profile_id, _ = _lagged_session()
    session.current_well.cuttings.append(CuttingsSample("source-probe", 1040.0, 1045.0, lba_odour="Recorded"))
    controller.select_projection(profile_id, LagCorrectionAxisMode.SOURCE)
    raw = interpretation_geology_snapshot(session)
    assert raw is not None
    controller.select_projection(profile_id, LagCorrectionAxisMode.CORRECTED)
    assert session.current_dataset.active_index.index_type is IndexType.MD
    assert not supports_saved_md_geology(session.current_dataset)
    assert interpretation_geology_snapshot(session) is None
    assert geology_for_dataset(raw, session.current_dataset) is None
    with pytest.raises(ValueError, match="explicit metre MD"):
        correlate_gas_interval_with_well_geology(session, top_depth=1040.0, bottom_depth=1045.0)
    controller.select_projection(profile_id, LagCorrectionAxisMode.SOURCE)
    assert interpretation_geology_snapshot(session) == raw


@pytest.mark.parametrize("output", ("pdf", "xlsx", "readable_xlsx"))
@pytest.mark.parametrize("coordinate", ("lag", "tvd", "feet", "unknown"))
def test_export_apis_reject_unaligned_selected_evidence_before_touching_targets(tmp_path, output, coordinate):
    from test_interpretation_geology_evidence_signed_pdf import _actual_source
    from geoworkbench.printing.hydrocarbon_interpretation_report import export_hydrocarbon_interpretation_pdf, HydrocarbonInterpretationPdfError
    from geoworkbench.data.hydrocarbon_interpretation_export import export_hydrocarbon_interpretation_xlsx
    from geoworkbench.data.hydrocarbon_interpretation_export_readable import export_readable_hydrocarbon_interpretation_xlsx

    session, report, evidence = _actual_source()
    dataset = session.current_dataset
    if coordinate == "lag":
        dataset.headers["LAG_PROFILE_ID"] = "unconfirmed-lag"
    elif coordinate == "tvd":
        dataset.active_index.index_type = IndexType.TVD
    else:
        dataset.active_index.unit = "ft" if coordinate == "feet" else None
    def export(path):
        if output == "pdf":
            return export_hydrocarbon_interpretation_pdf(report, path, dataset=dataset, geology_evidence=(evidence,), overwrite=True)
        exporter = export_hydrocarbon_interpretation_xlsx if output == "xlsx" else export_readable_hydrocarbon_interpretation_xlsx
        return exporter(report, dataset, path, geology_evidence=(evidence,), overwrite=True)
    suffix = ".pdf" if output == "pdf" else ".xlsx"
    missing = tmp_path / "new-parent" / ("report" + suffix)
    error = HydrocarbonInterpretationPdfError if output == "pdf" else ValueError
    with pytest.raises(error, match="metre MD"):
        export(missing)
    assert not missing.parent.exists()
    existing = tmp_path / ("existing" + suffix)
    existing.write_bytes(b"Existing report")
    with pytest.raises(error, match="metre MD"):
        export(existing)
    assert existing.read_bytes() == b"Existing report"
