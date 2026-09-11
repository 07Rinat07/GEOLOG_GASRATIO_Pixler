from copy import deepcopy
from dataclasses import asdict, replace

import pytest

from geoworkbench.domain.analysis_update import AnalysisField
from geoworkbench.domain.models import CuttingsSample, Well
from geoworkbench.services.well_analysis_apply import apply_prepared_analysis_update
from geoworkbench.services.well_analysis_update import (
    AnalysisSourceSample,
    AnalysisSourceValue,
    AnalysisUpdateError,
    analyze_well_analysis_update,
    prepare_well_analysis_update,
    well_analysis_state_sha256,
)


SHA = "a" * 64


def _prepared(well: Well):
    source = (
        AnalysisSourceSample(
            100.0,
            101.0,
            (
                AnalysisSourceValue(AnalysisField.CALCITE_PERCENT, 35.0),
                AnalysisSourceValue(AnalysisField.LBA_ODOUR, "oil"),
            ),
            "s1",
        ),
    )
    plan = analyze_well_analysis_update(
        well,
        source,
        selected_fields=(AnalysisField.CALCITE_PERCENT, AnalysisField.LBA_ODOUR),
        source_name="late-analysis.json",
        source_sha256=SHA,
    )
    prepared = prepare_well_analysis_update(
        well,
        source,
        plan,
        source_name="late-analysis.json",
        source_sha256=SHA,
        selected_changes=plan.changes,
    )
    assert prepared is not None
    return prepared


def _well() -> Well:
    return Well(
        "w1",
        "Well",
        cuttings=[
            CuttingsSample(
                "s1",
                100.0,
                101.0,
                description="manual geology",
            )
        ],
    )


def test_apply_commits_cuttings_history_and_revision_atomically():
    well = _well()
    prepared = _prepared(well)
    before_revision = well.content_revision

    record = apply_prepared_analysis_update(well, prepared)

    assert well.cuttings[0].calcite_percent == 35.0
    assert well.cuttings[0].lba_odour == "oil"
    assert well.cuttings[0].description == "manual geology"
    assert well.content_revision == before_revision + 1
    assert well.analysis_update_history == [record]
    assert record is prepared.record
    assert well_analysis_state_sha256(well) == record.well_sha256_after


@pytest.mark.parametrize("failure", ["wrong-well", "stale", "replay", "revision"])
def test_apply_rejects_invalid_or_stale_commit_without_mutation(failure):
    well = _well()
    prepared = _prepared(well)

    if failure == "wrong-well":
        prepared = replace(prepared, record=replace(prepared.record, well_id="other"))
    elif failure == "stale":
        well.cuttings[0].description = "edited after preview"
    elif failure == "replay":
        well.analysis_update_history.append(prepared.record)
    else:
        prepared = replace(prepared, revision=prepared.revision + 1)

    before = deepcopy(asdict(well))
    with pytest.raises(AnalysisUpdateError):
        apply_prepared_analysis_update(well, prepared)
    assert asdict(well) == before


def test_manual_fill_after_prepare_is_never_overwritten():
    well = _well()
    prepared = _prepared(well)
    well.cuttings[0].calcite_percent = 77.0
    before = deepcopy(asdict(well))

    with pytest.raises(AnalysisUpdateError, match="повторите просмотр"):
        apply_prepared_analysis_update(well, prepared)

    assert asdict(well) == before
    assert well.cuttings[0].calcite_percent == 77.0


@pytest.mark.parametrize("tamper", ["unapproved-field", "sample-count", "after-hash"])
def test_tampered_prepared_payload_never_partially_applies(tamper):
    well = _well()
    prepared = _prepared(well)

    if tamper == "unapproved-field":
        prepared.cuttings[0].description = "forged"
    elif tamper == "sample-count":
        prepared.cuttings.append(CuttingsSample("extra", 101.0, 102.0))
    else:
        prepared = replace(
            prepared,
            record=replace(prepared.record, well_sha256_after="b" * 64),
        )

    before = deepcopy(asdict(well))
    with pytest.raises(AnalysisUpdateError):
        apply_prepared_analysis_update(well, prepared)
    assert asdict(well) == before


def test_one_invalid_target_makes_multi_change_apply_all_or_nothing():
    well = _well()
    prepared = _prepared(well)
    forged_change = replace(prepared.record.changes[1], sample_id="missing")
    forged_record = replace(
        prepared.record,
        changes=(prepared.record.changes[0], forged_change),
    )
    prepared = replace(prepared, record=forged_record)
    before = deepcopy(asdict(well))

    with pytest.raises(AnalysisUpdateError, match="больше не существует"):
        apply_prepared_analysis_update(well, prepared)

    assert asdict(well) == before
