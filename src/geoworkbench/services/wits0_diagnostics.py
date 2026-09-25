from __future__ import annotations

from dataclasses import asdict, dataclass

from geoworkbench.acquisition.wits0 import Wits0Profile, wits0_profile_fingerprint
from geoworkbench.acquisition.wits0_capture import (
    Wits0CaptureConfig,
    Wits0CaptureSnapshot,
    Wits0ConnectionMode,
)
from geoworkbench.services.wits0_acquisition import Wits0AcquisitionSnapshot
from geoworkbench.services.wits0_import_review import (
    Wits0CustomProfile,
    Wits0DiscoverySnapshot,
)


@dataclass(frozen=True, slots=True)
class Wits0DiagnosticSnapshot:
    """Allowlisted WITS0 support state without raw measurements or network identity."""

    profile_id: str
    profile_version: int
    profile_schema_version: int
    profile_fingerprint: str
    encoding: str
    mode: str | None = None
    discovery_fingerprint: str | None = None
    custom_profile_id: str | None = None
    custom_profile_revision: int | None = None
    capture_state: str | None = None
    capture_frames_received: int = 0
    capture_parsed_fields: int = 0
    capture_parser_warnings: int = 0
    capture_parser_errors: int = 0
    capture_unknown_records: int = 0
    capture_unknown_fields: int = 0
    capture_sequence_gaps: int = 0
    capture_sequence_duplicates: int = 0
    capture_sequence_out_of_order: int = 0
    capture_errors: int = 0
    capture_dropped_ui_events: int = 0
    acquisition_state: str | None = None
    acquisition_pending_records: int = 0
    acquisition_frames_submitted: int = 0
    acquisition_frames_skipped: int = 0
    acquisition_records_enqueued: int = 0
    acquisition_records_applied: int = 0
    acquisition_backpressure_count: int = 0

    def as_dict(self) -> dict[str, object]:
        return asdict(self)


def build_wits0_diagnostic_snapshot(
    profile: Wits0Profile,
    *,
    config: Wits0CaptureConfig | None = None,
    selected_mode: Wits0ConnectionMode | None = None,
    capture: Wits0CaptureSnapshot | None = None,
    discovery: Wits0DiscoverySnapshot | None = None,
    custom_profile: Wits0CustomProfile | None = None,
    acquisition: Wits0AcquisitionSnapshot | None = None,
) -> Wits0DiagnosticSnapshot:
    """Build diagnostics only from already-sanitized metadata/counter snapshots."""

    return Wits0DiagnosticSnapshot(
        profile_id=profile.profile_id,
        profile_version=profile.version,
        profile_schema_version=profile.schema_version,
        profile_fingerprint=wits0_profile_fingerprint(profile),
        encoding=profile.encoding,
        mode=(
            config.mode.value
            if config is not None
            else selected_mode.value if selected_mode is not None else None
        ),
        discovery_fingerprint=discovery.fingerprint if discovery is not None else None,
        custom_profile_id=(
            custom_profile.custom_profile_id if custom_profile is not None else None
        ),
        custom_profile_revision=(
            custom_profile.revision if custom_profile is not None else None
        ),
        capture_state=capture.state.value if capture is not None else None,
        capture_frames_received=capture.frames_received if capture is not None else 0,
        capture_parsed_fields=capture.parsed_fields if capture is not None else 0,
        capture_parser_warnings=capture.parser_warnings if capture is not None else 0,
        capture_parser_errors=capture.parser_errors if capture is not None else 0,
        capture_unknown_records=capture.unknown_records if capture is not None else 0,
        capture_unknown_fields=capture.unknown_fields if capture is not None else 0,
        capture_sequence_gaps=capture.sequence_gaps if capture is not None else 0,
        capture_sequence_duplicates=(
            capture.sequence_duplicates if capture is not None else 0
        ),
        capture_sequence_out_of_order=(
            capture.sequence_out_of_order if capture is not None else 0
        ),
        capture_errors=capture.errors if capture is not None else 0,
        capture_dropped_ui_events=(
            capture.dropped_ui_events if capture is not None else 0
        ),
        acquisition_state=acquisition.state.value if acquisition is not None else None,
        acquisition_pending_records=(
            acquisition.pending_records if acquisition is not None else 0
        ),
        acquisition_frames_submitted=(
            acquisition.frames_submitted if acquisition is not None else 0
        ),
        acquisition_frames_skipped=(
            acquisition.frames_skipped if acquisition is not None else 0
        ),
        acquisition_records_enqueued=(
            acquisition.records_enqueued if acquisition is not None else 0
        ),
        acquisition_records_applied=(
            acquisition.records_applied if acquisition is not None else 0
        ),
        acquisition_backpressure_count=(
            acquisition.backpressure_count if acquisition is not None else 0
        ),
    )


__all__ = ["Wits0DiagnosticSnapshot", "build_wits0_diagnostic_snapshot"]
