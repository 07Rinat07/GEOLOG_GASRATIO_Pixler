from __future__ import annotations

import csv
import re
from dataclasses import dataclass
from pathlib import Path

import numpy as np

from geoworkbench.domain.models import (
    CurveData,
    CurveMetadata,
    Dataset,
    DatasetIndex,
    DatasetKind,
    DepthDomain,
    IndexRole,
    IndexType,
    new_id,
)
from geoworkbench.services.index_detection import (
    IndexCandidate,
    IndexColumn,
    detect_index_candidates,
)
from geoworkbench.services.time_normalization import normalize_iso8601_strings
from geoworkbench.services.time_normalization import normalize_date_time_columns


class CsvImportError(RuntimeError):
    pass


@dataclass(frozen=True, slots=True)
class CsvImportPlan:
    encoding: str = "utf-8-sig"
    delimiter: str | None = None
    index_column: str | None = None
    time_column: str | None = None
    date_format: str = "%Y-%m-%d"
    time_format: str = "%H:%M:%S"
    timezone: str | None = None
    null_tokens: tuple[str, ...] = ("", "NULL", "NA", "N/A", "NAN", "-999.25")

    def __post_init__(self) -> None:
        if not self.encoding.strip():
            raise ValueError("Кодировка CSV не может быть пустой")
        if self.delimiter is not None and len(self.delimiter) != 1:
            raise ValueError("Разделитель CSV должен состоять из одного символа")
        if not self.null_tokens:
            raise ValueError("Нужно указать хотя бы один маркер отсутствующих данных")
        if self.time_column is not None and (not self.date_format or not self.time_format):
            raise ValueError("Для DATE+TIME нужны форматы обеих колонок")


@dataclass(frozen=True, slots=True)
class CsvProbe:
    path: Path
    encoding: str
    delimiter: str
    columns: tuple[str, ...]
    preview_rows: tuple[tuple[str, ...], ...]


@dataclass(frozen=True, slots=True)
class CsvImportResult:
    dataset: Dataset
    delimiter: str
    encoding: str
    row_count: int


_HEADER_WITH_UNIT = re.compile(r"^(?P<name>.+?)\s*\[(?P<unit>[^\[\]]+)\]\s*$")


def probe_csv(path: str | Path, plan: CsvImportPlan | None = None) -> CsvProbe:
    source = _validate_source(path)
    selected = plan or CsvImportPlan()
    try:
        text = source.read_text(encoding=selected.encoding)
    except (LookupError, UnicodeDecodeError, OSError) as exc:
        raise CsvImportError(f"Не удалось прочитать CSV в кодировке {selected.encoding}") from exc
    delimiter = selected.delimiter or _detect_delimiter(text)
    rows = list(csv.reader(text.splitlines(), delimiter=delimiter))
    if not rows:
        raise CsvImportError("CSV-файл пуст")
    columns = tuple(cell.strip() for cell in rows[0])
    _validate_columns(columns)
    preview = tuple(tuple(cell.strip() for cell in row) for row in rows[1:6])
    return CsvProbe(source, selected.encoding, delimiter, columns, preview)


def import_csv(
    path: str | Path,
    plan: CsvImportPlan,
    *,
    kind: DatasetKind = DatasetKind.USER,
) -> CsvImportResult:
    if plan.index_column is None:
        raise CsvImportError("Нужно явно выбрать индексную колонку CSV")
    probe = probe_csv(path, plan)
    try:
        index_position = probe.columns.index(plan.index_column)
    except ValueError as exc:
        raise CsvImportError(f"Индексная колонка не найдена: {plan.index_column}") from exc
    time_position: int | None = None
    if plan.time_column is not None:
        if plan.time_column == plan.index_column:
            raise CsvImportError("Колонки DATE и TIME должны различаться")
        try:
            time_position = probe.columns.index(plan.time_column)
        except ValueError as exc:
            raise CsvImportError(f"Колонка TIME не найдена: {plan.time_column}") from exc
    try:
        with probe.path.open("r", encoding=probe.encoding, newline="") as stream:
            rows = list(csv.reader(stream, delimiter=probe.delimiter))
    except (UnicodeDecodeError, OSError, csv.Error) as exc:
        raise CsvImportError(f"Не удалось разобрать CSV: {probe.path.name}") from exc
    data_rows = rows[1:]
    if not data_rows:
        raise CsvImportError("CSV не содержит строк данных")
    width = len(probe.columns)
    for number, row in enumerate(data_rows, start=2):
        if len(row) != width:
            raise CsvImportError(f"Строка {number}: ожидалось колонок {width}, получено {len(row)}")
    null_tokens = {token.strip().casefold() for token in plan.null_tokens}
    if time_position is None:
        index_values, candidate, index_mnemonic, index_unit = _parse_index_column(
            data_rows,
            index_position,
            plan.index_column,
            null_tokens,
        )
    else:
        index_values, candidate, index_mnemonic, index_unit = _parse_composite_index(
            data_rows,
            index_position,
            time_position,
            plan,
            null_tokens,
        )
    domain = {
        "tvd": DepthDomain.TVD,
        "tvdss": DepthDomain.TVDSS,
        "relative_time": DepthDomain.TIME,
        "datetime": DepthDomain.TIME,
    }.get(candidate.index_type.value, DepthDomain.MD)
    dataset_id = new_id()
    if candidate.index_type is IndexType.DATETIME:
        index_id = f"{dataset_id}:csv-index"
        typed_index = DatasetIndex(
            index_id,
            index_mnemonic,
            candidate.index_type,
            candidate.role,
            index_unit,
            index_values,
            confidence=candidate.confidence,
            evidence=candidate.evidence,
            datetime_format=candidate.datetime_format,
            timezone=candidate.timezone,
        )
        dataset = Dataset(
            dataset_id,
            probe.path.stem,
            kind,
            domain,
            np.arange(len(data_rows), dtype=np.float64),
            source_path=probe.path,
            indexes={index_id: typed_index},
            active_index_id=index_id,
        )
    else:
        dataset = Dataset(
            dataset_id,
            probe.path.stem,
            kind,
            domain,
            index_values,
            source_path=probe.path,
        )
        dataset.active_index.mnemonic = index_mnemonic
        dataset.active_index.unit = index_unit
        dataset.active_index.index_type = candidate.index_type
        dataset.active_index.role = candidate.role
        dataset.active_index.confidence = candidate.confidence
        dataset.active_index.evidence = candidate.evidence
    for position, header in enumerate(probe.columns):
        if position == index_position or position == time_position:
            continue
        mnemonic, unit = _split_header(header)
        curve_id = new_id()
        dataset.curves[curve_id] = CurveData(
            CurveMetadata(
                curve_id,
                mnemonic,
                mnemonic.upper(),
                unit,
                header,
                dataset_id,
                provenance=f"csv:{probe.path.name}",
            ),
            _parse_numeric_column(data_rows, position, header, null_tokens),
        )
    return CsvImportResult(dataset, probe.delimiter, probe.encoding, len(data_rows))


def _parse_numeric_column(
    rows: list[list[str]],
    position: int,
    name: str,
    null_tokens: set[str],
) -> np.ndarray:
    values = np.empty(len(rows), dtype=np.float64)
    for index, row in enumerate(rows):
        text = row[position].strip()
        if text.casefold() in null_tokens:
            values[index] = np.nan
            continue
        try:
            values[index] = float(text.replace(",", "."))
        except ValueError as exc:
            raise CsvImportError(
                f"Колонка {name}, строка {index + 2}: ожидалось число, получено {text!r}"
            ) from exc
    return values


def _parse_index_column(
    rows: list[list[str]],
    position: int,
    header: str,
    null_tokens: set[str],
) -> tuple[np.ndarray, IndexCandidate, str, str | None]:
    mnemonic, unit = _split_header(header)
    try:
        numeric = _parse_numeric_column(rows, position, header, null_tokens)
    except CsvImportError as numeric_error:
        raw = np.asarray(
            [
                "" if row[position].strip().casefold() in null_tokens else row[position].strip()
                for row in rows
            ]
        )
        normalized = normalize_iso8601_strings(raw)
        if normalized is None or any(
            "смешаны значения" in warning for warning in normalized.warnings
        ):
            raise numeric_error
        candidate = detect_index_candidates([IndexColumn("csv-index", mnemonic, unit, None, raw)])[
            0
        ]
        return normalized.values, candidate, mnemonic, unit
    candidate = detect_index_candidates([IndexColumn("csv-index", mnemonic, unit, None, numeric)])[
        0
    ]
    return numeric, candidate, mnemonic, unit


def _parse_composite_index(
    rows: list[list[str]],
    date_position: int,
    time_position: int,
    plan: CsvImportPlan,
    null_tokens: set[str],
) -> tuple[np.ndarray, IndexCandidate, str, None]:
    dates = np.asarray(
        [
            ""
            if row[date_position].strip().casefold() in null_tokens
            else row[date_position].strip()
            for row in rows
        ]
    )
    times = np.asarray(
        [
            ""
            if row[time_position].strip().casefold() in null_tokens
            else row[time_position].strip()
            for row in rows
        ]
    )
    try:
        normalized = normalize_date_time_columns(
            dates,
            times,
            date_format=plan.date_format,
            time_format=plan.time_format,
            timezone_name=plan.timezone,
        )
    except ValueError as exc:
        raise CsvImportError(f"Не удалось нормализовать DATE+TIME: {exc}") from exc
    mnemonic = f"{plan.index_column}_{plan.time_column}"
    candidate = IndexCandidate(
        "csv-composite-index",
        mnemonic,
        IndexType.DATETIME,
        IndexRole.TIME,
        1.0,
        (f"явное объединение {plan.index_column} + {plan.time_column}",),
        normalized.warnings,
        normalized.datetime_format,
        normalized.timezone,
    )
    return normalized.values, candidate, mnemonic, None


def _detect_delimiter(text: str) -> str:
    try:
        return csv.Sniffer().sniff(text[:8192], delimiters=",;\t|").delimiter
    except csv.Error:
        header = text.splitlines()[0] if text.splitlines() else ""
        counts = {delimiter: header.count(delimiter) for delimiter in ",;\t|"}
        delimiter, count = max(counts.items(), key=lambda item: item[1])
        if count:
            return delimiter
        raise CsvImportError("Не удалось автоматически определить разделитель CSV") from None


def _validate_source(path: str | Path) -> Path:
    source = Path(path)
    if not source.exists():
        raise FileNotFoundError(source)
    if source.suffix.casefold() not in {".csv", ".txt"}:
        raise CsvImportError(f"Ожидался CSV/TXT-файл, получен: {source.suffix}")
    return source


def _validate_columns(columns: tuple[str, ...]) -> None:
    if not columns or any(not column for column in columns):
        raise CsvImportError("Заголовки CSV не должны быть пустыми")
    normalized = [column.casefold() for column in columns]
    if len(set(normalized)) != len(normalized):
        raise CsvImportError("Заголовки CSV не должны повторяться")


def _split_header(header: str) -> tuple[str, str | None]:
    match = _HEADER_WITH_UNIT.fullmatch(header)
    if match is None:
        return header.strip(), None
    return match.group("name").strip(), match.group("unit").strip()
