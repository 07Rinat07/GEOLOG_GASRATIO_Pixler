from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from io import BytesIO
from pathlib import Path
import re
import zipfile

from geoworkbench.importers.delphi_stream import (
    DelphiBinaryReader,
    DelphiComponentStream,
    DelphiStreamError,
    parse_delphi_component_stream,
)
from geoworkbench.importers.delphi_text_stream import (
    DelphiTextDocument,
    decode_delphi_text,
    parse_delphi_text_component_stream,
)
from geoworkbench.importers.skf_importer import (
    SkfImportError,
    SkfImportResult,
    import_delphi_component_stream,
)


class LegacyGeoSightImportError(ValueError):
    """Raised when a legacy GeoSight form source cannot be imported safely."""


class LegacyGeoSightSourceKind(StrEnum):
    TEXT_FORM = "text_form"
    BINARY_FORM = "binary_form"
    GSF_DESCRIPTOR = "gsf_descriptor"
    GS2_CONTAINER = "gs2_container"
    UNKNOWN = "unknown"


@dataclass(frozen=True, slots=True)
class LegacyGeoSightImportBundle:
    source: Path
    source_kind: LegacyGeoSightSourceKind
    results: tuple[SkfImportResult, ...]
    active_index: int | None = None
    companion_source: Path | None = None

    def __post_init__(self) -> None:
        if not self.results:
            raise ValueError("Legacy GeoSight import bundle requires at least one form")
        if self.active_index is not None and not 0 <= self.active_index < len(self.results):
            raise ValueError("active_index is outside imported form range")

    @property
    def active_result(self) -> SkfImportResult:
        if self.active_index is not None:
            return self.results[self.active_index]
        return self.results[0]


def detect_geosight_source(payload: bytes) -> LegacyGeoSightSourceKind:
    """Classify legacy GeoSight sources by content, never by extension alone."""

    if not payload:
        return LegacyGeoSightSourceKind.UNKNOWN
    if len(payload) > DelphiBinaryReader.MAX_STREAM_BYTES:
        return LegacyGeoSightSourceKind.UNKNOWN
    if zipfile.is_zipfile(BytesIO(payload)):
        return LegacyGeoSightSourceKind.GS2_CONTAINER
    if DelphiBinaryReader.SIGNATURE in payload:
        return LegacyGeoSightSourceKind.BINARY_FORM

    try:
        text, _encoding = decode_delphi_text(payload)
    except DelphiStreamError:
        return LegacyGeoSightSourceKind.UNKNOWN

    normalized = text.lstrip("\ufeff\r\n\t ")
    if re.search(
        r"(?mi)^\s*(?:object|inherited|inline)\s+"
        r"(?:[^:\s]+\s*:\s*)?[A-Za-z_]\w*\s*$",
        normalized,
    ):
        return LegacyGeoSightSourceKind.TEXT_FORM
    if _looks_like_gsf_descriptor(normalized):
        return LegacyGeoSightSourceKind.GSF_DESCRIPTOR
    return LegacyGeoSightSourceKind.UNKNOWN


def import_legacy_geosight_file(source: str | Path) -> LegacyGeoSightImportBundle:
    path = Path(source).expanduser()
    _validate_source_file(path)
    try:
        payload = path.read_bytes()
    except OSError as exc:
        raise LegacyGeoSightImportError(
            f"Не удалось прочитать legacy GeoSight форму: {path}"
        ) from exc

    kind = detect_geosight_source(payload)
    if kind is LegacyGeoSightSourceKind.GS2_CONTAINER:
        raise LegacyGeoSightImportError(
            "Файл является ZIP-контейнером GeoScape II GS2 с данными, "
            "а не legacy-формой. Используйте импорт GS2."
        )
    if kind is LegacyGeoSightSourceKind.TEXT_FORM:
        return _import_text_form(path, payload)
    if kind is LegacyGeoSightSourceKind.BINARY_FORM:
        result = _convert_binary(
            payload,
            source_name=path.name,
            source_format="geosight-delphi-binary",
        )
        return LegacyGeoSightImportBundle(
            source=path,
            source_kind=kind,
            results=(result,),
        )
    if kind is LegacyGeoSightSourceKind.GSF_DESCRIPTOR:
        companion = _resolve_descriptor_companion(path)
        _validate_source_file(companion)
        try:
            companion_payload = companion.read_bytes()
        except OSError as exc:
            raise LegacyGeoSightImportError(
                f"Не удалось прочитать бинарную форму GeoSight: {companion}"
            ) from exc
        companion_kind = detect_geosight_source(companion_payload)
        if companion_kind is not LegacyGeoSightSourceKind.BINARY_FORM:
            raise LegacyGeoSightImportError(
                f"Связанный GRC не содержит Delphi TPF0 stream: {companion.name}"
            )
        result = _convert_binary(
            companion_payload,
            source_name=path.name,
            source_format="geosight-gsf-grc",
        )
        return LegacyGeoSightImportBundle(
            source=path,
            source_kind=kind,
            results=(result,),
            companion_source=companion,
        )
    raise LegacyGeoSightImportError(
        "Формат legacy GeoSight формы не распознан. "
        "Ожидается текстовый Delphi DFM, бинарный TPF0 или GSF-дескриптор."
    )


def _import_text_form(
    path: Path,
    payload: bytes,
) -> LegacyGeoSightImportBundle:
    try:
        document = parse_delphi_text_component_stream(payload)
    except DelphiStreamError as exc:
        raise LegacyGeoSightImportError(str(exc)) from exc

    results: list[SkfImportResult] = []
    for index, stream in enumerate(document.streams()):
        result = import_delphi_component_stream(
            stream,
            source_payload=payload,
            source_name=path.name,
            source_format="geosight-delphi-text",
        )
        page_name = _page_name(document, index)
        if page_name:
            result.form.name = page_name[:160]
            result.header_template.name = f"{page_name} — GeoSight header"[:200]
        results.append(result)

    return LegacyGeoSightImportBundle(
        source=path,
        source_kind=LegacyGeoSightSourceKind.TEXT_FORM,
        results=tuple(results),
        active_index=document.active_page,
    )


def _convert_binary(
    payload: bytes,
    *,
    source_name: str,
    source_format: str,
) -> SkfImportResult:
    try:
        stream = parse_delphi_component_stream(payload)
    except DelphiStreamError as exc:
        raise LegacyGeoSightImportError(str(exc)) from exc
    try:
        return import_delphi_component_stream(
            stream,
            source_payload=payload,
            source_name=source_name,
            source_format=source_format,
        )
    except (SkfImportError, ValueError) as exc:
        raise LegacyGeoSightImportError(str(exc)) from exc


def _page_name(document: DelphiTextDocument, index: int) -> str:
    raw = document.page_name(index).strip()
    if not raw:
        return ""
    if raw.startswith("'") or raw.startswith("#"):
        return _decode_pascal_caption(raw)
    return raw


def _decode_pascal_caption(value: str) -> str:
    result: list[str] = []
    index = 0
    while index < len(value):
        char = value[index]
        if char.isspace() or char == "+":
            index += 1
            continue
        if char == "'":
            index += 1
            chunk: list[str] = []
            while index < len(value):
                if value[index] != "'":
                    chunk.append(value[index])
                    index += 1
                    continue
                if index + 1 < len(value) and value[index + 1] == "'":
                    chunk.append("'")
                    index += 2
                    continue
                index += 1
                break
            result.append("".join(chunk))
            continue
        if char == "#":
            index += 1
            end = index
            while end < len(value) and value[end].isdigit():
                end += 1
            if end == index:
                return value
            codepoint = int(value[index:end])
            if 0 <= codepoint <= 0x10FFFF:
                result.append(chr(codepoint))
            index = end
            continue
        return value
    return "".join(result)


def _looks_like_gsf_descriptor(text: str) -> bool:
    return bool(
        re.search(r"(?mi)^\s*\[Form\]\s*$", text)
        and re.search(r"(?mi)^\s*Class\s*=\s*[^\r\n]+$", text)
    )


def _resolve_descriptor_companion(source: Path) -> Path:
    stem = source.stem
    candidates = [
        source.with_suffix(".grc"),
        source.with_name(f"{stem}Form.grc"),
    ]
    numbered = re.fullmatch(r"(?P<base>.*?)(?P<suffix>\(\d+\))", stem)
    if numbered is not None:
        candidates.append(
            source.with_name(
                f"{numbered.group('base')}Form{numbered.group('suffix')}.grc"
            )
        )

    seen: set[Path] = set()
    for candidate in candidates:
        if candidate in seen:
            continue
        seen.add(candidate)
        if candidate.is_file() and not candidate.is_symlink():
            return candidate
    expected = ", ".join(candidate.name for candidate in candidates)
    raise LegacyGeoSightImportError(
        f"Для GSF-дескриптора не найден связанный GRC: {expected}"
    )


def _validate_source_file(path: Path) -> None:
    if not path.is_file() or path.is_symlink():
        raise LegacyGeoSightImportError(
            f"Источник legacy GeoSight должен быть обычным файлом: {path}"
        )
    try:
        size = path.stat().st_size
    except OSError as exc:
        raise LegacyGeoSightImportError(
            f"Не удалось получить сведения о legacy GeoSight файле: {path}"
        ) from exc
    if size > DelphiBinaryReader.MAX_STREAM_BYTES:
        raise LegacyGeoSightImportError(
            "Legacy GeoSight файл превышает безопасный предел 64 МБ"
        )


__all__ = [
    "LegacyGeoSightImportBundle",
    "LegacyGeoSightImportError",
    "LegacyGeoSightSourceKind",
    "detect_geosight_source",
    "import_legacy_geosight_file",
]
