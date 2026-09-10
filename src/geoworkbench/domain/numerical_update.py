"""Persisted, bounded audit of explicitly selected numerical LAS updates."""
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
import math
import re


class NumericalUpdateKind(str, Enum):
    APPEND = "append"
    FILL = "fill"
    CORRECT = "correct"


@dataclass(frozen=True, slots=True)
class NumericalCellChange:
    kind: NumericalUpdateKind
    curve_id: str
    mnemonic: str
    source_row: int
    target_row: int | None
    index_value: str
    before: float | None
    after: float

    def __post_init__(self) -> None:
        if not isinstance(self.kind, NumericalUpdateKind):
            raise ValueError("Неизвестная операция обновления")
        for value in (self.curve_id, self.mnemonic, self.index_value):
            if not isinstance(value, str) or not value.strip() or len(value) > 2000:
                raise ValueError("Некорректная ячейка обновления")
        for row in (self.source_row, self.target_row):
            if row is not None and (type(row) is not int or row < 0):
                raise ValueError("Некорректный номер строки обновления")
        if self.source_row is None or ((self.target_row is None) != (self.kind is NumericalUpdateKind.APPEND)):
            raise ValueError("Строка не соответствует операции обновления")
        for measurement in (self.before, self.after):
            if measurement is not None and (type(measurement) not in (int, float) or not math.isfinite(measurement)):
                raise ValueError("Значение обновления должно быть конечным числом")
        if self.after is None or ((self.before is not None) != (self.kind is NumericalUpdateKind.CORRECT)):
            raise ValueError("Значения не соответствуют операции обновления")


@dataclass(frozen=True, slots=True)
class NumericalUpdateRecord:
    update_id: str
    source_name: str
    source_sha256: str
    imported_at: str
    dataset_sha256_before: str
    dataset_sha256_after: str
    rows_added: int
    changes: tuple[NumericalCellChange, ...]

    def __post_init__(self) -> None:
        for value in (self.update_id, self.source_name, self.imported_at):
            if not isinstance(value, str) or not value.strip() or len(value) > 2000:
                raise ValueError("Некорректная запись обновления")
        for digest in (self.source_sha256, self.dataset_sha256_before, self.dataset_sha256_after):
            if not isinstance(digest, str) or not re.fullmatch(r"[0-9a-f]{64}", digest):
                raise ValueError("Некорректный SHA-256 обновления")
        if type(self.rows_added) is not int or self.rows_added < 0:
            raise ValueError("Некорректный счётчик новых строк")
        if not isinstance(self.changes, tuple) or len(self.changes) > 10_000:
            raise ValueError("Слишком большой список изменений")
        if not all(isinstance(c, NumericalCellChange) and c.kind is not NumericalUpdateKind.APPEND for c in self.changes):
            raise ValueError("История ячеек содержит некорректные изменения")
        keys = [(c.curve_id, c.target_row) for c in self.changes]
        if len(set(keys)) != len(keys) or not (self.rows_added or self.changes):
            raise ValueError("Пустая или повторяющаяся запись обновления")
