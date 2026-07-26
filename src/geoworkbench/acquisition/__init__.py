"""Runtime source adapters for append-only acquisition.

The package is intentionally independent from Qt and from the project mutation layer.
Source adapters capture immutable raw input first; semantic parsing and committing to an
``AcquisitionSession`` are separate stages.
"""

from geoworkbench.acquisition.wits0 import (
    WITS0_PROFILE_SCHEMA_VERSION,
    Wits0FieldDefinition,
    Wits0FrameDecoder,
    Wits0FrameError,
    Wits0FrameTooLargeError,
    Wits0Profile,
    Wits0ProfileError,
    Wits0RecordDefinition,
    iter_wits0_frames,
    load_builtin_wits0_profile,
    load_wits0_profile,
)
from geoworkbench.acquisition.wits0_parser import (
    Wits0Diagnostic,
    Wits0DiagnosticCode,
    Wits0DiagnosticSeverity,
    Wits0ParsedField,
    Wits0ParsedFrame,
    Wits0Parser,
    Wits0ParserConfig,
    Wits0SequenceStatus,
    Wits0SequenceTracker,
    Wits0StreamProcessor,
    iter_parsed_wits0_frames,
    process_wits0_chunks,
)
from geoworkbench.acquisition.wits0_capture import (
    Wits0CaptureConfig,
    Wits0CaptureEngine,
    Wits0CaptureEvent,
    Wits0CaptureEventKind,
    Wits0CaptureSnapshot,
    Wits0CaptureState,
    Wits0ConnectionMode,
    Wits0RawCaptureWriter,
)

__all__ = [
    "WITS0_PROFILE_SCHEMA_VERSION",
    "Wits0CaptureConfig",
    "Wits0Diagnostic",
    "Wits0DiagnosticCode",
    "Wits0DiagnosticSeverity",
    "Wits0ParsedField",
    "Wits0ParsedFrame",
    "Wits0Parser",
    "Wits0ParserConfig",
    "Wits0SequenceStatus",
    "Wits0SequenceTracker",
    "Wits0StreamProcessor",
    "Wits0CaptureEngine",
    "Wits0CaptureEvent",
    "Wits0CaptureEventKind",
    "Wits0CaptureSnapshot",
    "Wits0CaptureState",
    "Wits0ConnectionMode",
    "Wits0FieldDefinition",
    "Wits0FrameDecoder",
    "Wits0FrameError",
    "Wits0FrameTooLargeError",
    "Wits0Profile",
    "Wits0ProfileError",
    "Wits0RawCaptureWriter",
    "Wits0RecordDefinition",
    "iter_parsed_wits0_frames",
    "iter_wits0_frames",
    "process_wits0_chunks",
    "load_builtin_wits0_profile",
    "load_wits0_profile",
]
