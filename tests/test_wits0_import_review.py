from __future__ import annotations

from dataclasses import replace
from io import BytesIO
from pathlib import Path

import pytest

from geoworkbench.acquisition import (
    Wits0StreamProcessor,
    iter_parsed_wits0_frames,
    load_builtin_wits0_profile,
    process_wits0_chunks,
)
from geoworkbench.domain.models import DepthDomain, IndexRole, IndexType
from geoworkbench.services.uom_dictionary import QuantityClass
from geoworkbench.services.wits0_import_review import (
    Wits0ChannelKey,
    Wits0ChannelOverride,
    Wits0DiscoveryAccumulator,
    Wits0ImportReviewController,
    Wits0ImportReviewValidationError,
    acquisition_schema_digest,
    discover_wits0_frames,
    load_wits0_custom_profile,
    next_wits0_custom_profile_revision,
    save_wits0_custom_profile,
)


def _frame(record: int, sequence: int, *lines: str) -> bytes:
    body = (
        "&&",
        f"{record:02d}01SG-8",
        f"{record:02d}0201",
        f"{record:02d}03{record}",
        f"{record:02d}04{sequence}",
        f"{record:02d}05260727",
        f"{record:02d}060215450",
        f"{record:02d}070",
        *lines,
        "!!",
    )
    return "\r\n".join(body).encode("ascii")


def _snapshot():  # type: ignore[no-untyped-def]
    profile = load_builtin_wits0_profile()
    processor = Wits0StreamProcessor(profile)
    frames = processor.append(
        _frame(2, 1, "0208123.4", "021011.2", "029912.5")
        + _frame(2, 2, "0208123.6", "021012.0", "029913.5")
    )
    return profile, discover_wits0_frames(profile, frames)


def test_discovery_collects_all_data_fields_and_stable_samples() -> None:
    profile, snapshot = _snapshot()

    assert snapshot.profile_id == profile.profile_id
    assert snapshot.frame_count == 2
    assert snapshot.datetime_observation_count == 2
    assert [item.key.source_id for item in snapshot.channels] == ["0208", "0210", "0299"]
    depth = snapshot.channel("0208")
    assert depth is not None
    assert depth.source_mnemonic == "HOLE_DEPTH"
    assert depth.numeric_min == 123.4
    assert depth.numeric_max == 123.6
    assert depth.samples == ("123.4", "123.6")
    unknown = snapshot.channel(Wits0ChannelKey(2, 99))
    assert unknown is not None and not unknown.known
    assert len(snapshot.fingerprint) == 64


def test_live_and_replay_produce_identical_discovery_snapshot() -> None:
    profile = load_builtin_wits0_profile()
    raw = _frame(1, 10, "0108100", "011311.1") + _frame(
        2, 7, "0208100", "021012.2"
    )
    live = discover_wits0_frames(
        profile,
        process_wits0_chunks(
            (raw[:3], raw[3:31], raw[31:79], raw[79:]),
            profile=profile,
        ),
    )
    replay = discover_wits0_frames(
        profile,
        iter_parsed_wits0_frames(BytesIO(raw), profile=profile, chunk_size=5),
    )

    assert live == replay


def test_initial_review_maps_semantics_uom_and_time_depth_candidates() -> None:
    profile, snapshot = _snapshot()
    controller = Wits0ImportReviewController()

    candidates = controller.index_candidates(snapshot)
    plan = controller.initial_plan(snapshot, dataset_name="SG-8 WITS0")
    review = controller.preview(snapshot, profile, plan)

    assert [item.candidate_id for item in candidates][:2] == [
        "header:datetime",
        "field:0208",
    ]
    assert candidates[0].role is IndexRole.TIME
    assert candidates[0].index_type is IndexType.DATETIME
    assert candidates[1].role is IndexRole.DEPTH
    assert candidates[1].canonical_uom == "m"
    assert review.error_count == 0
    rop = next(item for item in review.channels if item.key.source_id == "0210")
    assert rop.canonical_mnemonic == "ROP"
    assert rop.canonical_kind == "drilling.rop"
    assert rop.quantity_class is QuantityClass.LINEAR_VELOCITY
    assert rop.source_uom == "M/HR"
    assert rop.canonical_uom == "m/h"


def test_atomic_commit_builds_immutable_time_schema_and_versioned_profile(
    tmp_path: Path,
) -> None:
    profile, snapshot = _snapshot()
    controller = Wits0ImportReviewController()
    plan = controller.initial_plan(snapshot, dataset_name="SG-8 WITS0")

    commit = controller.commit(
        snapshot,
        profile,
        plan,
        created_at="2026-07-27T03:00:00.000Z",
    )

    assert commit.schema.name == "SG-8 WITS0"
    assert commit.schema.depth_domain is DepthDomain.TIME
    assert commit.schema.indexes[0].role is IndexRole.TIME
    assert commit.schema.indexes[0].index_type is IndexType.DATETIME
    assert commit.schema.indexes[0].timezone == "UTC"
    assert len(commit.schema.curves) == 3
    assert commit.schema_digest == acquisition_schema_digest(commit.schema)
    assert len(commit.schema_digest) == 64
    assert commit.custom_profile.revision == 1

    saved = save_wits0_custom_profile(commit.custom_profile, tmp_path)
    loaded = load_wits0_custom_profile(saved)
    assert loaded == commit.custom_profile
    assert next_wits0_custom_profile_revision(tmp_path, loaded.custom_profile_id) == 2
    with pytest.raises(FileExistsError):
        save_wits0_custom_profile(commit.custom_profile, tmp_path)


def test_depth_index_is_not_duplicated_as_curve_and_hidden_channel_is_omitted() -> None:
    profile, snapshot = _snapshot()
    controller = Wits0ImportReviewController()
    plan = controller.initial_plan(snapshot)
    candidates = controller.index_candidates(snapshot)
    depth_candidate = next(item for item in candidates if item.candidate_id == "field:0208")
    overrides = []
    for item in plan.channels:
        if item.key.source_id == "0210":
            overrides.append(replace(item, import_enabled=False))
        else:
            overrides.append(item)
    depth_plan = replace(
        plan,
        index_candidate_id=depth_candidate.candidate_id,
        index_mnemonic="MD",
        index_type=IndexType.MD,
        index_unit="m",
        timezone=None,
        channels=tuple(overrides),
    )

    commit = controller.commit(snapshot, profile, depth_plan)

    assert commit.schema.depth_domain is DepthDomain.MD
    assert commit.schema.indexes[0].role is IndexRole.DEPTH
    assert commit.schema.indexes[0].unit == "m"
    source_ids = {
        curve.metadata.provenance.removeprefix("wits0:")
        for curve in commit.schema.curves
    }
    assert "0208" not in source_ids
    assert "0210" not in source_ids
    assert source_ids == {"0299"}


def test_manual_rename_and_semantic_override_are_frozen_in_schema() -> None:
    profile, snapshot = _snapshot()
    controller = Wits0ImportReviewController()
    plan = controller.initial_plan(snapshot)
    changed: list[Wits0ChannelOverride] = []
    for item in plan.channels:
        if item.key.source_id == "0299":
            changed.append(
                replace(
                    item,
                    canonical_mnemonic="CUSTOM_SENSOR",
                    canonical_kind="manual.custom_sensor",
                    quantity_class=QuantityClass.DIMENSIONLESS,
                    source_uom="1",
                    canonical_uom="1",
                )
            )
        else:
            changed.append(item)
    plan = replace(plan, channels=tuple(changed))

    commit = controller.commit(snapshot, profile, plan)
    curve = next(
        item.metadata
        for item in commit.schema.curves
        if item.metadata.provenance == "wits0:0299"
    )

    assert curve.canonical_mnemonic == "CUSTOM_SENSOR"
    assert curve.unit == "1"
    assert curve.semantic is not None
    assert curve.semantic.canonical_kind == "manual.custom_sensor"
    assert curve.semantic.quantity_class is QuantityClass.DIMENSIONLESS
    assert curve.semantic.matched_by == "manual_wits0_import_review"


def test_review_rejects_stale_discovery_and_required_numeric_conversion() -> None:
    profile, snapshot = _snapshot()
    controller = Wits0ImportReviewController()
    plan = controller.initial_plan(snapshot)
    accumulator = Wits0DiscoveryAccumulator(profile)
    accumulator.observe_many(
        Wits0StreamProcessor(profile).append(
            _frame(2, 3, "0208124", "021013", "02311300")
        )
    )
    changed_snapshot = accumulator.snapshot()

    stale = controller.preview(changed_snapshot, profile, plan)
    assert stale.error_count > 0
    assert any(issue.code == "stale-discovery" for issue in stale.issues)

    conversion_overrides = tuple(
        replace(item, canonical_uom="ft") if item.key.source_id == "0208" else item
        for item in plan.channels
    )
    conversion_plan = replace(plan, channels=conversion_overrides)
    review = controller.preview(snapshot, profile, conversion_plan)
    assert review.error_count > 0
    depth = next(item for item in review.channels if item.key.source_id == "0208")
    assert any(issue.code == "uom-conversion-required" for issue in depth.issues)
    with pytest.raises(Wits0ImportReviewValidationError):
        controller.commit(snapshot, profile, conversion_plan)


def test_non_numeric_field_cannot_enter_acquisition_schema() -> None:
    profile = load_builtin_wits0_profile()
    frame = Wits0StreamProcessor(profile).append(
        _frame(3, 1, "0399CONNECTION-1")
    )[0]
    snapshot = discover_wits0_frames(profile, (frame,))
    controller = Wits0ImportReviewController()
    plan = controller.initial_plan(snapshot)
    text_override = replace(plan.channels[0], import_enabled=True)
    plan = replace(plan, channels=(text_override,))

    review = controller.preview(snapshot, profile, plan)

    assert review.error_count > 0
    assert any(
        issue.code == "non-numeric-channel"
        for channel in review.channels
        for issue in channel.issues
    )


def test_discovery_fingerprint_changes_only_when_mapping_relevant_shape_changes() -> None:
    profile = load_builtin_wits0_profile()
    processor = Wits0StreamProcessor(profile)
    accumulator = Wits0DiscoveryAccumulator(profile)
    first = processor.append(_frame(2, 1, "0208123.4", "021011.2"))[0]
    accumulator.observe(first)
    fingerprint = accumulator.snapshot().fingerprint

    # More values for the same record/item set update statistics but do not invalidate
    # an already confirmed Import Review schema.
    second = processor.append(_frame(2, 2, "0208124.0", "021012.0"))[0]
    accumulator.observe(second)
    assert accumulator.snapshot().fingerprint == fingerprint

    # A new record/item changes the mapping surface and must make the review stale.
    third = processor.append(_frame(2, 3, "0208125.0", "021013.0", "02311300"))[0]
    accumulator.observe(third)
    assert accumulator.snapshot().fingerprint != fingerprint


def test_custom_profile_from_other_base_profile_is_rejected() -> None:
    profile, snapshot = _snapshot()
    controller = Wits0ImportReviewController()
    commit = controller.commit(snapshot, profile, controller.initial_plan(snapshot))
    foreign = replace(commit.custom_profile, base_profile_version=profile.version + 1)

    with pytest.raises(ValueError, match="another base profile"):
        controller.initial_plan(snapshot, custom_profile=foreign)
