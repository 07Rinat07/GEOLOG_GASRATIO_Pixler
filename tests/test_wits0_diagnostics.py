from __future__ import annotations

from dataclasses import replace
import json
from pathlib import Path
import re

from geoworkbench.acquisition.wits0 import (
    load_builtin_wits0_profile,
    wits0_profile_fingerprint,
)
from geoworkbench.acquisition.wits0_capture import (
    Wits0CaptureConfig,
    Wits0CaptureSnapshot,
    Wits0CaptureState,
    Wits0ConnectionMode,
)
from geoworkbench.domain.models import IndexType
from geoworkbench.services.wits0_acquisition import (
    Wits0AcquisitionSnapshot,
    Wits0AcquisitionState,
)
from geoworkbench.services.wits0_diagnostics import build_wits0_diagnostic_snapshot
from geoworkbench.services.wits0_import_review import (
    Wits0CustomProfile,
    Wits0DiscoveryAccumulator,
)


def test_wits0_profile_fingerprint_is_canonical_and_version_sensitive() -> None:
    profile = load_builtin_wits0_profile()

    fingerprint = wits0_profile_fingerprint(profile)

    assert re.fullmatch(r"[0-9a-f]{64}", fingerprint)
    assert wits0_profile_fingerprint(profile) == fingerprint
    assert wits0_profile_fingerprint(
        replace(profile, version=profile.version + 1)
    ) != fingerprint


def test_wits0_diagnostic_snapshot_is_allowlisted_and_omits_source_identity(
    tmp_path: Path,
) -> None:
    profile = load_builtin_wits0_profile()
    config = Wits0CaptureConfig(
        mode=Wits0ConnectionMode.TCP_CLIENT,
        host="SECRET-HOST",
        port=2041,
        raw_directory=tmp_path / "SECRET-RAW-DIRECTORY",
        source_name="SECRET-SOURCE-NAME",
        encoding=profile.encoding,
    )
    capture = Wits0CaptureSnapshot(
        state=Wits0CaptureState.CONNECTED,
        current_peer="SECRET-PEER",
        current_raw_file="SECRET-RAW-FILE",
        frames_received=17,
        parsed_fields=51,
        parser_warnings=2,
        parser_errors=3,
        unknown_records=4,
        unknown_fields=5,
        sequence_gaps=6,
        sequence_duplicates=7,
        sequence_out_of_order=8,
        errors=9,
        dropped_ui_events=10,
    )
    acquisition = Wits0AcquisitionSnapshot(
        state=Wits0AcquisitionState.OPEN,
        session_id="SECRET-ACQUISITION-SESSION",
        pending_records=11,
        queue_capacity=100,
        queue_remaining_capacity=89,
        frames_submitted=12,
        batches_normalized=13,
        frames_skipped=14,
        records_enqueued=15,
        records_applied=16,
        backpressure_count=1,
        checkpoints_created=2,
        last_checkpoint_sequence=10,
        last_applied_sequence=16,
        last_error="SECRET-LAST-ERROR",
    )
    discovery = Wits0DiscoveryAccumulator(profile).snapshot()
    custom_profile = Wits0CustomProfile(
        custom_profile_id="SECRET-CUSTOMER-WELL-RIG",
        revision=3,
        title="SECRET-CUSTOM-PROFILE-TITLE",
        base_profile_id=profile.profile_id,
        base_profile_version=profile.version,
        discovery_fingerprint=discovery.fingerprint,
        index_candidate_id="header_datetime",
        index_mnemonic="DEPT",
        index_type=IndexType.MD,
        index_unit="m",
        timezone=None,
        channels=(),
        created_at="2026-09-25T00:00:00Z",
    )

    snapshot = build_wits0_diagnostic_snapshot(
        profile,
        config=config,
        capture=capture,
        discovery=discovery,
        custom_profile=custom_profile,
        acquisition=acquisition,
    )
    payload = snapshot.as_dict()
    rendered = json.dumps(payload, ensure_ascii=False, sort_keys=True)

    assert payload["profile_id"] == profile.profile_id
    assert payload["profile_version"] == profile.version
    assert payload["profile_fingerprint"] == wits0_profile_fingerprint(profile)
    assert payload["encoding"] == profile.encoding
    assert payload["mode"] == Wits0ConnectionMode.TCP_CLIENT.value
    assert payload["discovery_fingerprint"] == discovery.fingerprint
    assert payload["custom_profile_revision"] == 3
    assert payload["capture_frames_received"] == 17
    assert payload["capture_parser_errors"] == 3
    assert payload["acquisition_frames_submitted"] == 12
    assert payload["acquisition_frames_skipped"] == 14
    assert payload["acquisition_records_applied"] == 16
    assert "SECRET" not in rendered
    for forbidden_key in (
        "host",
        "port",
        "peer",
        "raw_directory",
        "current_raw_file",
        "source_name",
        "session_id",
        "last_error",
        "custom_profile_id",
    ):
        assert forbidden_key not in payload
