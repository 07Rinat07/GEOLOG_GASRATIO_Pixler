from __future__ import annotations

from dataclasses import replace
from datetime import datetime, timezone

import pytest

from geoworkbench.domain.models import Well
from geoworkbench.importers.etp12.models import (
    Etp12ChannelBatch,
    Etp12ChannelMetadata,
    Etp12ChannelPoint,
    Etp12Protocol,
)
from geoworkbench.services.etp12_acquisition import (
    Etp12AcquisitionConfig,
    Etp12AcquisitionRuntime,
    Etp12BackpressurePolicy,
    Etp12ChannelNormalizer,
    Etp12NormalizationCode,
    extract_point_hashes,
)
from geoworkbench.services.etp12_import_review import (
    Etp12DiscoveryAccumulator,
    Etp12ImportReviewController,
    restore_etp12_import_review_commit,
)


def _metadata(channel_id: int = 10) -> dict[str, Etp12ChannelMetadata]:
    return {
        "rop": Etp12ChannelMetadata(
            channel_id=channel_id,
            channel_uri="eml:///witsml21.Channel(rop)",
            channel_name="ROP",
            data_kind="double",
            uom="ft/h",
            index_kind="dateTime",
            start_index=1_000_000,
            end_index=2_000_000,
            description="Rate of penetration",
            index_uom="us",
            index_name="Time",
        ),
        "spp": Etp12ChannelMetadata(
            channel_id=channel_id + 1,
            channel_uri="eml:///witsml21.Channel(spp)",
            channel_name="SPP",
            data_kind="double",
            uom="kPa",
            index_kind="dateTime",
            start_index=1_000_000,
            end_index=2_000_000,
            description="Standpipe pressure",
            index_uom="us",
            index_name="Time",
        ),
    }


def _batch(
    *,
    generation: int = 1,
    first_id: int = 10,
    index: int = 1_000_000,
    rop: float = 32.80839895,
    spp: float = 12_500.0,
    message_id: int = 101,
) -> Etp12ChannelBatch:
    return Etp12ChannelBatch(
        subscription_id="sub-main",
        points=(
            Etp12ChannelPoint(first_id, index, rop),
            Etp12ChannelPoint(first_id + 1, index, spp),
        ),
        received_at_utc=datetime(2026, 7, 27, 5, 0, tzinfo=timezone.utc),
        message_id=message_id,
        correlation_id=0,
        protocol=Etp12Protocol.CHANNEL_SUBSCRIBE,
        generation=generation,
        channel_uris={
            first_id: "eml:///witsml21.Channel(rop)",
            first_id + 1: "eml:///witsml21.Channel(spp)",
        },
    )


def _commit():  # type: ignore[no-untyped-def]
    metadata = _metadata()
    discovery = Etp12DiscoveryAccumulator("sub-main")
    discovery.update_metadata(metadata, generation=1)
    discovery.observe(_batch())
    snapshot = discovery.snapshot()
    controller = Etp12ImportReviewController()
    plan = controller.initial_plan(snapshot)
    commit = controller.commit(snapshot, plan)
    return metadata, snapshot, commit


def test_discovery_identity_is_uri_based_across_reconnect_channel_ids() -> None:
    discovery = Etp12DiscoveryAccumulator("sub-main")
    discovery.update_metadata(_metadata(10), generation=1)
    first = discovery.snapshot()
    discovery.update_metadata(_metadata(110), generation=2)
    second = discovery.snapshot()

    assert first.fingerprint == second.fingerprint
    assert second.generation == 2
    assert {item.channel_id for item in second.channels} == {110, 111}


def test_import_review_builds_immutable_schema_and_uom_conversion_plan() -> None:
    _metadata_map, snapshot, commit = _commit()

    assert commit.review.error_count == 0
    assert commit.review.subscription_id == "sub-main"
    assert commit.schema_digest
    assert commit.schema.indexes[0].timezone == "UTC"
    by_name = {item.canonical_mnemonic: item for item in commit.review.channels}
    assert by_name["ROP"].source_uom == "ft/h"
    assert by_name["ROP"].canonical_uom == "m/h"
    assert by_name["ROP"].conversion_required


def test_normalizer_groups_channel_points_and_converts_units() -> None:
    metadata, _snapshot, commit = _commit()
    result = Etp12ChannelNormalizer(commit, metadata).normalize(_batch())

    assert result.accepted
    assert len(result.batches) == 1
    batch = result.batches[0]
    assert batch.index_values[0][1] == 1_000_000_000
    values = {item.canonical_mnemonic: item.value for item in batch.measurements}
    assert values["ROP"] == pytest.approx(10.0)
    assert values["SPP"] == pytest.approx(123.3654083395)
    assert len(batch.point_hashes) == 2


def test_normalizer_rejects_other_subscription_without_mutation() -> None:
    metadata, _snapshot, commit = _commit()
    other = replace(_batch(), subscription_id="other")

    result = Etp12ChannelNormalizer(commit, metadata).normalize(other)

    assert not result.accepted
    assert result.diagnostics[0].code is Etp12NormalizationCode.SUBSCRIPTION_MISMATCH


def test_runtime_deduplicates_exact_overlap_after_reconnect_with_new_ids() -> None:
    metadata, _snapshot, commit = _commit()
    well = Well("well-1", "Well 1")
    runtime = Etp12AcquisitionRuntime(
        well,
        commit,
        session_id="etp-session-1",
        metadata=metadata,
        config=Etp12AcquisitionConfig(overlap_window_points=100),
    )

    runtime.submit_channel_batch(_batch())
    runtime.flush()
    assert len(runtime.controller.dataset.depth) == 1

    runtime.update_metadata(_metadata(110))
    duplicate = _batch(generation=2, first_id=110, message_id=201)
    runtime.submit_channel_batch(duplicate)

    snapshot = runtime.snapshot()
    assert snapshot.pending_records == 0
    assert snapshot.overlap_points_dropped == 2
    assert snapshot.overlap_batches_dropped == 1
    assert len(runtime.controller.dataset.depth) == 1

    changed = _batch(generation=2, first_id=110, rop=39.37007874, message_id=202)
    runtime.submit_channel_batch(changed)
    runtime.flush()
    assert len(runtime.controller.dataset.depth) == 2
    rop_curve = next(
        item for item in runtime.controller.dataset.curves.values()
        if item.metadata.canonical_mnemonic == "ROP"
    )
    assert rop_curve.values[-1] == pytest.approx(12.0)


def test_dedup_window_is_restored_from_open_append_only_session() -> None:
    metadata, _snapshot, commit = _commit()
    well = Well("well-1", "Well 1")
    first = Etp12AcquisitionRuntime(
        well,
        commit,
        session_id="etp-session-1",
        metadata=metadata,
    )
    first.submit_channel_batch(_batch())
    first.flush()
    hashes = extract_point_hashes(first.session.records[0].source)
    assert len(hashes) == 2

    resumed = Etp12AcquisitionRuntime(
        well,
        commit,
        session_id="etp-session-1",
        metadata=_metadata(110),
        session=first.session,
    )
    resumed.submit_channel_batch(_batch(generation=2, first_id=110, message_id=202))

    assert resumed.snapshot().overlap_points_dropped == 2
    assert resumed.controller.pending_count == 0
    assert len(resumed.controller.dataset.depth) == 1


def test_runtime_backpressure_is_bounded_and_atomic() -> None:
    metadata, _snapshot, commit = _commit()
    well = Well("well-1", "Well 1")
    runtime = Etp12AcquisitionRuntime(
        well,
        commit,
        session_id="etp-session-1",
        metadata=metadata,
        config=Etp12AcquisitionConfig(
            max_pending_records=1,
            backpressure_policy=Etp12BackpressurePolicy.RAISE,
        ),
    )
    # Two distinct indexes in one ChannelData message normalize to two rows.
    two_rows = replace(
        _batch(),
        points=(
            Etp12ChannelPoint(10, 1_000_000, 32.80839895),
            Etp12ChannelPoint(11, 1_000_000, 12_500.0),
            Etp12ChannelPoint(10, 2_000_000, 39.37007874),
            Etp12ChannelPoint(11, 2_000_000, 12_700.0),
        ),
    )

    with pytest.raises(Exception):
        runtime.submit_channel_batch(two_rows)

    assert runtime.controller.pending_count == 0
    assert runtime.session.records == []
    assert len(runtime.controller.dataset.depth) == 0


def test_controlled_close_creates_final_checkpoint() -> None:
    metadata, _snapshot, commit = _commit()
    well = Well("well-1", "Well 1")
    runtime = Etp12AcquisitionRuntime(
        well,
        commit,
        session_id="etp-session-1",
        metadata=metadata,
    )
    runtime.submit_channel_batch(_batch())

    checkpoint = runtime.close(closed_at="2026-07-27T06:00:00Z")

    assert checkpoint.sequence == 1
    assert runtime.session.state.value == "closed"
    assert runtime.session.final_audit_digest == checkpoint.audit_digest


def test_open_etp_session_roundtrips_and_restores_overlap_window(tmp_path) -> None:
    from geoworkbench.domain.models import Project
    from geoworkbench.storage.atomic_json import save_project
    from geoworkbench.storage.project_codec import load_project

    metadata, _snapshot, commit = _commit()
    well = Well("well-1", "Well 1")
    runtime = Etp12AcquisitionRuntime(
        well,
        commit,
        session_id="etp-session-1",
        metadata=metadata,
    )
    runtime.submit_channel_batch(_batch())
    runtime.flush()

    target = tmp_path / "etp-project.json"
    save_project(Project("project-1", "Project", wells={well.well_id: well}), target)
    loaded = load_project(target)
    loaded_well = loaded.wells[well.well_id]
    loaded_session = loaded_well.acquisition_sessions["etp-session-1"]

    resumed = Etp12AcquisitionRuntime(
        loaded_well,
        commit,
        session_id="etp-session-1",
        metadata=_metadata(110),
        session=loaded_session,
    )
    resumed.submit_channel_batch(_batch(generation=2, first_id=110, message_id=303))

    assert resumed.snapshot().overlap_points_dropped == 2
    assert resumed.controller.pending_count == 0
    assert resumed.session.last_sequence == 1


def test_import_review_commit_can_be_restored_from_persisted_schema() -> None:
    metadata, snapshot, commit = _commit()
    well = Well("well-1", "Well 1")
    runtime = Etp12AcquisitionRuntime(
        well, commit, session_id="etp-session-1", metadata=metadata
    )
    runtime.submit_channel_batch(_batch())
    runtime.flush()

    restored = restore_etp12_import_review_commit(runtime.session, snapshot)

    assert restored.schema == commit.schema
    assert restored.schema_digest == commit.schema_digest
    assert [item.channel_uri for item in restored.plan.channels] == [
        item.channel_uri for item in commit.plan.channels
    ]
