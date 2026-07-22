from __future__ import annotations

from dataclasses import dataclass, field
from enum import IntEnum, StrEnum
from pathlib import Path
from typing import Any

import numpy as np
from numpy.typing import NDArray


class ParadoxFieldType(IntEnum):
    ALPHA = 1
    DATE = 2
    SHORT = 3
    LONG = 4
    CURRENCY = 5
    NUMBER = 6
    LOGICAL = 9
    MEMO_BLOB = 12
    BLOB = 13
    FORMATTED_MEMO = 14
    OLE = 15
    GRAPHIC = 16
    TIME = 20
    TIMESTAMP = 21
    AUTOINCREMENT = 22
    BCD = 23
    BYTES = 24

    @classmethod
    def label(cls, value: int) -> str:
        try:
            return cls(value).name
        except ValueError:
            return f"UNKNOWN_{value}"


class IssueSeverity(StrEnum):
    INFO = "info"
    WARNING = "warning"
    ERROR = "error"
    CRITICAL = "critical"


class DatasetClassification(StrEnum):
    DEPTH = "depth"
    TIME = "time"
    TIME_WITH_DEPTH = "time_with_depth"
    MIXED = "mixed"
    UNDEFINED = "undefined"


class DuplicateDepthPolicy(StrEnum):
    KEEP_ALL = "keep_all"
    FIRST = "first"
    LAST = "last"
    MEAN = "mean"
    MEDIAN = "median"


@dataclass(frozen=True, slots=True)
class ParadoxBundle:
    main: Path
    primary_index: Path | None = None
    table_view: Path | None = None
    family: Path | None = None

    @property
    def files(self) -> tuple[Path, ...]:
        return tuple(
            item
            for item in (self.main, self.primary_index, self.table_view, self.family)
            if item is not None
        )


@dataclass(frozen=True, slots=True)
class ParadoxHeader:
    record_size: int
    header_size: int
    file_type: int
    max_table_size_kib: int
    record_count: int
    file_blocks: int
    first_block: int
    last_block: int
    field_count: int
    file_version_id: int
    code_page: int
    table_name: str | None

    @property
    def block_size(self) -> int:
        return self.max_table_size_kib * 1024

    @property
    def version_label(self) -> str:
        known = {
            3: "3.x",
            4: "3.5",
            5: "4.x",
            6: "4.x",
            7: "4.x",
            8: "4.x",
            9: "4.x",
            10: "5.x",
            11: "5.x",
            12: "7.x",
        }
        return known.get(self.file_version_id, f"ID {self.file_version_id}")


@dataclass(frozen=True, slots=True)
class ParadoxField:
    ordinal: int
    name: str
    type_code: int
    size: int
    offset: int

    @property
    def type_name(self) -> str:
        return ParadoxFieldType.label(self.type_code)

    @property
    def is_numeric(self) -> bool:
        return self.type_code in {
            ParadoxFieldType.DATE,
            ParadoxFieldType.SHORT,
            ParadoxFieldType.LONG,
            ParadoxFieldType.CURRENCY,
            ParadoxFieldType.NUMBER,
            ParadoxFieldType.TIME,
            ParadoxFieldType.TIMESTAMP,
            ParadoxFieldType.AUTOINCREMENT,
            ParadoxFieldType.BCD,
            ParadoxFieldType.LOGICAL,
        }


@dataclass(frozen=True, slots=True)
class ParadoxIssue:
    severity: IssueSeverity
    code: str
    message: str
    file: Path
    record_number: int | None = None
    field_name: str | None = None
    file_offset: int | None = None
    field_type: str | None = None
    details: dict[str, Any] = field(default_factory=dict)


@dataclass(slots=True)
class ParadoxColumn:
    field: ParadoxField
    values: NDArray[Any]
    raw_values: NDArray[Any] | None = None
    filled_count: int = 0
    null_count: int = 0
    minimum: float | None = None
    maximum: float | None = None
    is_empty: bool = False


@dataclass(slots=True)
class ParadoxTable:
    source: Path
    bundle: ParadoxBundle
    header: ParadoxHeader
    fields: tuple[ParadoxField, ...]
    columns: dict[str, ParadoxColumn]
    rows_read: int
    issues: list[ParadoxIssue] = field(default_factory=list)

    def preview(self, head: int = 20, tail: int = 20) -> tuple[tuple[Any, ...], ...]:
        total = self.rows_read
        indexes = list(range(min(head, total)))
        tail_start = max(len(indexes), total - max(0, tail))
        indexes.extend(range(tail_start, total))
        names = [field.name for field in self.fields]
        return tuple(tuple(self.columns[name].values[index] for name in names) for index in indexes)


@dataclass(frozen=True, slots=True)
class IndexCandidate:
    field_name: str
    role: str
    confidence: float
    evidence: tuple[str, ...]
    warnings: tuple[str, ...]
    converted_preview: str | None = None


@dataclass(frozen=True, slots=True)
class QualitySummary:
    classification: DatasetClassification
    depth_candidates: tuple[IndexCandidate, ...]
    time_candidates: tuple[IndexCandidate, ...]
    issues: tuple[ParadoxIssue, ...]


@dataclass(frozen=True, slots=True)
class ChannelMapping:
    source_name: str
    mnemonic: str
    unit: str = ""
    description: str = ""
    import_enabled: bool = True


@dataclass(frozen=True, slots=True)
class ParadoxImportPlan:
    classification: DatasetClassification = DatasetClassification.UNDEFINED
    depth_field: str | None = None
    time_field: str | None = None
    active_role: str = "auto"
    null_value: float = -999.25
    sort_by_index: bool = False
    mappings: tuple[ChannelMapping, ...] = ()
    profile_name: str | None = None
    duplicate_depth_policy: DuplicateDepthPolicy = DuplicateDepthPolicy.KEEP_ALL
    drop_empty_channels: bool = False
    language: str = "ru"


@dataclass(frozen=True, slots=True)
class ParadoxImportResult:
    dataset: Any
    table: ParadoxTable
    quality: QualitySummary
    imported_channels: int
    skipped_channels: int
    skipped_records: int
