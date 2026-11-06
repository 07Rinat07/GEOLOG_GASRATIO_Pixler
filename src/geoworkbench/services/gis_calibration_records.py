"""Bounded, detached GIS parameter records; loading never activates calibration."""

from __future__ import annotations

from dataclasses import asdict, dataclass, fields
from datetime import datetime, timedelta, timezone
from hashlib import sha256
import json
from math import isfinite
import os
from pathlib import Path
import re
import tempfile
from typing import Any

import numpy as np

from geoworkbench.domain.models import Dataset, IndexRole, IndexType
from geoworkbench.services.gis_input_inventory import GisCurveInput
from geoworkbench.services.gis_reference_calibration import (
    GisReferenceCalibration, validate_gis_reference_calibration,
)
from geoworkbench.services.gis_reference_input_review import (
    GisReferenceInputReview, review_gis_reference_input,
)


MAX_RECORD_BYTES = 65_536
MAX_ID_CHARS = 200
MAX_EVIDENCE_CHARS = 2000
_PARAMETERS = {
    "igr-linear-1": {"clean_reference_api", "shale_reference_api"},
    "density-porosity-1": {"matrix_density_g_cm3", "fluid_density_g_cm3"},
}


@dataclass(frozen=True, slots=True)
class GisArrayFingerprint:
    dtype: str
    shape: tuple[int, ...]
    sha256: str


@dataclass(frozen=True, slots=True)
class GisAxisRecord:
    mnemonic: str
    index_type: IndexType
    role: IndexRole
    unit: str | None
    confidence: float
    evidence: tuple[str, ...]
    datetime_format: str | None
    timezone: str | None


@dataclass(frozen=True, slots=True)
class GisCalibrationSource:
    review: GisReferenceInputReview
    axis: GisAxisRecord
    depths: GisArrayFingerprint
    values: GisArrayFingerprint
    metadata_sha256: str


@dataclass(frozen=True, slots=True)
class SavedGisCalibrationRecord:
    recorded_at_utc: str
    calibration_id: str
    tool_id: str
    reviewer: str
    applicability_reference: str
    md_bounds: tuple[float, float]
    parameters: tuple[tuple[str, float], ...]
    source: GisCalibrationSource

    @property
    def method_id(self) -> str:
        return self.source.review.method_id

    @property
    def curve_key(self) -> str:
        return self.source.review.curve_key


def export_gis_calibration_record(
    dataset: Dataset, calibration: GisReferenceCalibration, destination: str | Path,
    *, overwrite: bool = False,
) -> Path:
    """Atomically save parameters from a still-valid runtime calibration.

    The record contains fingerprints, not source arrays, authorization or a saved
    result. The original runtime identity guards remain mandatory during export.
    """
    validate_gis_reference_calibration(dataset, calibration)
    target = Path(destination)
    _guard_destination(dataset, target)
    source = _source_snapshot(dataset, calibration.source.method_id, calibration.source.curve_key)
    payload = {
        "schema_version": 1,
        "artifact_kind": "gis_calibration_parameters",
        "review_status": "parameters_only_not_active_calibration",
        "recorded_at_utc": datetime.now(timezone.utc).isoformat(),
        "calibration_id": calibration.calibration_id,
        "tool_id": calibration.tool_id,
        "reviewer": calibration.reviewer,
        "applicability_reference": calibration.applicability_reference,
        "md_bounds": list(calibration.md_bounds),
        "parameters": dict(calibration.parameters),
        "source": asdict(source),
    }
    content = (json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True,
                          allow_nan=False) + "\n").encode("utf-8")
    # Validate the same bounded format that the reader accepts before any write.
    record = _decode_record(content)
    temporary: Path | None = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="wb", dir=target.parent, prefix=".gis-calibration-", suffix=".tmp",
            delete=False,
        ) as stream:
            temporary = Path(stream.name)
            stream.write(content)
            stream.flush()
            os.fsync(stream.fileno())
        validate_gis_reference_calibration(dataset, calibration)
        validate_gis_calibration_record_source(dataset, record)
        _guard_destination(dataset, target)
        if overwrite:
            os.replace(temporary, target)
        else:
            os.link(temporary, target)
        return target
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)


def load_gis_calibration_record(
    path: str | Path, *, dataset: Dataset,
) -> SavedGisCalibrationRecord:
    """Read parameters only for an exactly matching persisted source.

    Matching permits explicit prefill, not calculation or geological approval.
    Reopening a project creates new arrays; the runtime calibration must still
    be created anew by an explicit operator action.
    """
    with Path(path).open("rb") as stream:
        content = stream.read(MAX_RECORD_BYTES + 1)
    record = _decode_record(content)
    validate_gis_calibration_record_source(dataset, record)
    return record


def validate_gis_calibration_record_source(
    dataset: Dataset, record: SavedGisCalibrationRecord,
) -> None:
    """Compare current source content without constructing a calibration."""
    if not isinstance(record, SavedGisCalibrationRecord):
        raise ValueError("A saved GIS parameter record is required")
    current = _source_snapshot(dataset, record.method_id, record.curve_key)
    if current != record.source:
        raise ValueError("GIS parameter record source differs from the current source")


def _source_snapshot(dataset: Dataset, method_id: str, curve_key: str) -> GisCalibrationSource:
    review = review_gis_reference_input(dataset, method_id=method_id, curve_key=curve_key)
    if not review.ready_for_calibration or review.curve is None:
        raise ValueError("GIS parameter record source is unavailable")
    axis = dataset.active_index
    curve = dataset.curves[curve_key]
    metadata = json.dumps(asdict(curve.metadata), ensure_ascii=True, sort_keys=True,
                          allow_nan=False, separators=(",", ":"))
    return GisCalibrationSource(
        review=review,
        axis=GisAxisRecord(axis.mnemonic, axis.index_type, axis.role, axis.unit,
                           float(axis.confidence), tuple(axis.evidence),
                           axis.datetime_format, axis.timezone),
        depths=_fingerprint(axis.values), values=_fingerprint(curve.values),
        metadata_sha256=sha256(metadata.encode("utf-8")).hexdigest(),
    )


def _fingerprint(samples: np.ndarray) -> GisArrayFingerprint:
    return GisArrayFingerprint(
        samples.dtype.str, samples.shape,
        sha256(np.ascontiguousarray(samples).data).hexdigest(),
    )


def _guard_destination(dataset: Dataset, target: Path) -> None:
    if target.suffix.casefold() != ".json" or target.name.casefold().endswith(".geolog.json"):
        raise ValueError("GIS parameters require a separate JSON destination")
    if dataset.source_path is not None:
        original = Path(dataset.source_path)
        if target.resolve() == original.resolve() or (
            target.exists() and original.exists() and target.samefile(original)
        ):
            raise ValueError("GIS parameter destination must not replace the source file")


def _decode_record(content: bytes) -> SavedGisCalibrationRecord:
    if len(content) > MAX_RECORD_BYTES:
        raise ValueError("GIS parameter record exceeds the supported size")
    try:
        raw = json.loads(content.decode("utf-8"), object_pairs_hook=_unique_object,
                         parse_constant=_invalid_constant)
    except (UnicodeError, RecursionError) as exc:
        raise ValueError("Invalid GIS parameter JSON") from exc
    payload = _object(raw, {
        "schema_version", "artifact_kind", "review_status", "recorded_at_utc",
        "calibration_id", "tool_id", "reviewer", "applicability_reference",
        "md_bounds", "parameters", "source",
    })
    if (type(payload["schema_version"]) is not int or payload["schema_version"] != 1
            or payload["artifact_kind"] != "gis_calibration_parameters"
            or payload["review_status"] != "parameters_only_not_active_calibration"):
        raise ValueError("Unsupported GIS parameter record schema or status")
    recorded = _text(payload["recorded_at_utc"])
    instant = datetime.fromisoformat(recorded)
    if instant.tzinfo is None or instant.utcoffset() != timedelta(0):
        raise ValueError("GIS record time must include UTC")
    source = _parse_source(payload["source"])
    bounds = _bounds(payload["md_bounds"])
    assert source.review.curve is not None and source.review.curve.sample_md_bounds is not None
    observed = source.review.curve.sample_md_bounds
    if bounds[0] < observed[0] or bounds[1] > observed[1]:
        raise ValueError("GIS record scope exceeds source sample bounds")
    params = _object(payload["parameters"], _PARAMETERS[source.review.method_id])
    parameters = {key: _number(value) for key, value in params.items()}
    if source.review.method_id == "igr-linear-1":
        valid = parameters["shale_reference_api"] > parameters["clean_reference_api"]
    else:
        valid = parameters["matrix_density_g_cm3"] > parameters["fluid_density_g_cm3"] > 0
    if not valid:
        raise ValueError("Invalid GIS calibration parameter range")
    return SavedGisCalibrationRecord(
        recorded, _text(payload["calibration_id"]), _text(payload["tool_id"]),
        _text(payload["reviewer"]),
        _text(payload["applicability_reference"], limit=MAX_EVIDENCE_CHARS),
        bounds, tuple(sorted(parameters.items())), source,
    )


def _parse_source(value: Any) -> GisCalibrationSource:
    source = _object(value, {field.name for field in fields(GisCalibrationSource)})
    data = _object(source["review"], {field.name for field in fields(GisReferenceInputReview)})
    method = _text(data["method_id"])
    if method not in _PARAMETERS or data["issues"] != []:
        raise ValueError("Unsupported or unreviewed GIS source")
    curve = _parse_curve(data["curve"])
    review = GisReferenceInputReview(
        method, _text(data["dataset_id"]), _text(data["axis_id"]),
        _text(data["curve_key"]), _text(data["required_unit"]), curve, (),
    )
    if review.curve_key != curve.curve_key:
        raise ValueError("Inconsistent GIS curve key")
    axis = _object(source["axis"], {field.name for field in fields(GisAxisRecord)})
    axis_record = GisAxisRecord(
        _text(axis["mnemonic"]), IndexType(_text(axis["index_type"])),
        IndexRole(_text(axis["role"])), _optional_text(axis["unit"]),
        _confidence(axis["confidence"]), _texts(axis["evidence"]),
        _optional_text(axis["datetime_format"]), _optional_text(axis["timezone"]),
    )
    depths, values = _parse_fingerprint(source["depths"]), _parse_fingerprint(source["values"])
    if depths.shape != values.shape or curve.finite_sample_count > depths.shape[0]:
        raise ValueError("Inconsistent GIS sample shapes or counts")
    return GisCalibrationSource(review, axis_record, depths, values,
                                _digest(source["metadata_sha256"]))


def _parse_curve(value: Any) -> GisCurveInput:
    curve = _object(value, {field.name for field in fields(GisCurveInput)})
    if curve["issues"] != []:
        raise ValueError("GIS record requires a reviewed curve")
    return GisCurveInput(
        _text(curve["curve_key"]), _text(curve["curve_id"]),
        _text(curve["source_dataset_id"]), _text(curve["original_mnemonic"]),
        _optional_text(curve["canonical_mnemonic"]), _optional_text(curve["family"]),
        None if curve["semantic_confidence"] is None else _confidence(curve["semantic_confidence"]),
        _texts(curve["semantic_evidence"]), _optional_text(curve["unit"]),
        _text(curve["provenance"], limit=MAX_EVIDENCE_CHARS), _positive_int(curve["version"]),
        _positive_int(curve["finite_sample_count"]), _bounds(curve["sample_md_bounds"]), (),
    )


def _parse_fingerprint(value: Any) -> GisArrayFingerprint:
    data = _object(value, {"dtype", "shape", "sha256"})
    dtype = _text(data["dtype"])
    if not re.fullmatch(r"[<>=|][fiu](?:1|2|4|8|16)", dtype):
        raise ValueError("Invalid GIS sample dtype")
    try:
        decoded = np.dtype(dtype)
    except TypeError as exc:
        raise ValueError("Invalid GIS sample dtype") from exc
    if decoded.kind not in "fiu" or decoded.str != dtype:
        raise ValueError("Noncanonical GIS sample dtype")
    if not isinstance(data["shape"], list) or len(data["shape"]) != 1:
        raise ValueError("GIS samples must have a one-dimensional shape")
    return GisArrayFingerprint(dtype, (_positive_int(data["shape"][0]),), _digest(data["sha256"]))


def _object(value: Any, names: set[str]) -> dict[str, Any]:
    if not isinstance(value, dict) or set(value) != names:
        raise ValueError("Unexpected GIS parameter record fields")
    return value


def _text(value: Any, *, limit: int = MAX_ID_CHARS) -> str:
    if not isinstance(value, str) or not value.strip() or len(value) > limit:
        raise ValueError("GIS parameter text is missing or exceeds its limit")
    # JSON escapes can contain lone surrogates that Qt silently drops on prefill.
    try:
        value.encode("utf-8")
    except UnicodeError as exc:
        raise ValueError("GIS parameter text must contain valid Unicode") from exc
    return value


def _optional_text(value: Any) -> str | None:
    return None if value is None else _text(value)


def _texts(value: Any) -> tuple[str, ...]:
    if not isinstance(value, list) or len(value) > 128:
        raise ValueError("Invalid GIS evidence list")
    return tuple(_text(item, limit=MAX_EVIDENCE_CHARS) for item in value)


def _number(value: Any) -> float:
    if type(value) not in (float, int):
        raise ValueError("A finite JSON number is required")
    try:
        number = float(value)
    except OverflowError as exc:
        raise ValueError("A finite JSON number is required") from exc
    if not isfinite(number):
        raise ValueError("A finite JSON number is required")
    return number


def _confidence(value: Any) -> float:
    number = _number(value)
    if not 0 <= number <= 1:
        raise ValueError("GIS confidence must be between zero and one")
    return number


def _positive_int(value: Any) -> int:
    if type(value) is not int or not 0 < value <= 2**63 - 1:
        raise ValueError("A positive bounded JSON integer is required")
    return value


def _bounds(value: Any) -> tuple[float, float]:
    if not isinstance(value, list) or len(value) != 2:
        raise ValueError("Two explicit GIS MD bounds are required")
    bounds = (_number(value[0]), _number(value[1]))
    if bounds[0] > bounds[1]:
        raise ValueError("GIS MD bounds must be ordered")
    return bounds


def _digest(value: Any) -> str:
    if not isinstance(value, str) or re.fullmatch(r"[0-9a-f]{64}", value) is None:
        raise ValueError("Invalid GIS source fingerprint")
    return value


def _unique_object(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for name, value in pairs:
        if name in result:
            raise ValueError("Duplicate GIS parameter record key")
        result[name] = value
    return result


def _invalid_constant(value: str) -> Any:
    raise ValueError("Non-finite JSON values are not supported")
