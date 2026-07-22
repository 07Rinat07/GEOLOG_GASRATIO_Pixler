from __future__ import annotations

from dataclasses import dataclass, replace
from enum import StrEnum
import json
from pathlib import Path
from typing import Callable, Iterable

from .analysis import analyze_table
from .importer import default_mappings, import_paradox
from .models import DatasetClassification, IssueSeverity, ParadoxImportPlan, ParadoxTable
from .reader import read_paradox


class BatchStatus(StrEnum):
    SUCCESS = "success"
    WARNING = "warning"
    ERROR = "error"
    SKIPPED = "skipped"


@dataclass(frozen=True, slots=True)
class BatchItemResult:
    source: Path
    target: Path | None
    status: BatchStatus
    message: str
    records: int = 0
    channels: int = 0
    warnings: int = 0


def convert_batch(
    sources: Iterable[str | Path],
    output_directory: str | Path,
    *,
    mode: str = "depth",
    overwrite: bool = False,
    plan_factory: Callable[[Path, ParadoxTable], ParadoxImportPlan | None] | None = None,
    name_mask: str = "{source_name}_{mode}.las",
    progress: Callable[[str, int, int], None] | None = None,
    cancelled: Callable[[], bool] | None = None,
    language: str = "ru",
    translate: Callable[..., str] | None = None,
) -> tuple[BatchItemResult, ...]:
    output = Path(output_directory)
    output.mkdir(parents=True, exist_ok=True)
    source_items = tuple(sources)

    def message(key: str, **values: object) -> str:
        if translate is not None:
            return translate(key, **values)
        return _DEFAULT_MESSAGES.get(key, key).format(**values)

    # Validate target uniqueness before any file is written. A constant name
    # mask such as ``result.las`` is safe only for one source and one mode; for
    # several sources it would otherwise create one file and silently skip the
    # remaining operations as "already exists".
    planned_targets: dict[Path, Path] = {}
    for item in source_items:
        source = Path(item).expanduser().resolve()
        target = (output / _target_name(name_mask, source, mode)).resolve()
        previous = planned_targets.get(target)
        if previous is not None:
            raise ValueError(
                message(
                    "paradox.batch_duplicate_targets",
                    target=target.name,
                    first=previous.name,
                    second=source.name,
                )
            )
        planned_targets[target] = source

    results: list[BatchItemResult] = []
    total = len(source_items)
    for position, item in enumerate(source_items, start=1):
        if cancelled is not None and cancelled():
            raise RuntimeError(message("paradox.batch_cancelled"))
        source = Path(item).expanduser().resolve()
        if progress is not None:
            progress(source.name, position - 1, total)
        target = output / _target_name(name_mask, source, mode)
        if target.exists() and not overwrite:
            results.append(
                BatchItemResult(
                    source, target, BatchStatus.SKIPPED, message("paradox.batch_exists")
                )
            )
            continue
        try:
            table = read_paradox(source, cancelled=cancelled)
            quality = analyze_table(table)
            material_issues = [
                issue
                for issue in quality.issues
                if issue.severity
                in {IssueSeverity.WARNING, IssueSeverity.ERROR, IssueSeverity.CRITICAL}
            ]
            plan = plan_factory(source, table) if plan_factory is not None else None
            if plan is None:
                if quality.classification in {
                    DatasetClassification.MIXED,
                    DatasetClassification.UNDEFINED,
                }:
                    results.append(
                        BatchItemResult(
                            source,
                            None,
                            BatchStatus.ERROR,
                            message("paradox.batch_ambiguous"),
                            records=table.rows_read,
                            warnings=len(material_issues),
                        )
                    )
                    continue
                depth = quality.depth_candidates[0].field_name if quality.depth_candidates else None
                time = quality.time_candidates[0].field_name if quality.time_candidates else None
                if mode == "depth" and depth is None:
                    raise ValueError(message("paradox.batch_no_depth"))
                if mode == "time" and time is None:
                    raise ValueError(message("paradox.batch_no_time"))
                plan = ParadoxImportPlan(
                    quality.classification,
                    depth,
                    time,
                    mode,
                    -999.25,
                    False,
                    default_mappings(table, language=language),
                )
            plan = replace(plan, active_role=mode)
            if mode == "depth" and plan.depth_field is None:
                raise ValueError(message("paradox.batch_profile_no_depth"))
            if mode == "time" and plan.time_field is None:
                raise ValueError(message("paradox.batch_profile_no_time"))
            imported = import_paradox(
                source,
                plan,
                table=table,
                quality=quality,
                cancelled=cancelled,
            )
            from geoworkbench.data.las_adapter import export_las, import_las
            from geoworkbench.data.las_export_plan import LasExportPlan

            export_las(
                imported.dataset,
                target,
                overwrite=overwrite,
                plan=LasExportPlan(null_value=plan.null_value),
            )
            # Mandatory round-trip validation through the application's own reader.
            reopened = import_las(target)
            expected_rows = len(imported.dataset.active_index.values)
            if len(reopened.depth) != expected_rows:
                raise RuntimeError(
                    f"Round-trip LAS returned {len(reopened.depth)} rows instead of {expected_rows}"
                )
            status = BatchStatus.WARNING if material_issues else BatchStatus.SUCCESS
            result = BatchItemResult(
                source,
                target,
                status,
                message("paradox.batch_roundtrip_success"),
                records=table.rows_read,
                channels=imported.imported_channels,
                warnings=len(material_issues),
            )
            _write_log(result, imported.dataset.parameters, target.with_suffix(".import.json"))
            results.append(result)
        except Exception as exc:
            results.append(BatchItemResult(source, target, BatchStatus.ERROR, str(exc)))
        finally:
            if progress is not None:
                progress(source.name, position, total)
    return tuple(results)


_DEFAULT_MESSAGES = {
    "paradox.batch_cancelled": "Пакетная конвертация отменена пользователем",
    "paradox.batch_exists": "Результат уже существует",
    "paradox.batch_ambiguous": "Индекс неоднозначен; требуется профиль или ручная настройка",
    "paradox.batch_no_depth": "Не найден надёжный канал глубины",
    "paradox.batch_no_time": "Не найден надёжный канал времени",
    "paradox.batch_profile_no_depth": "Профиль не содержит канал глубины",
    "paradox.batch_profile_no_time": "Профиль не содержит канал времени",
    "paradox.batch_roundtrip_success": "LAS создан и повторно открыт текущим LAS-reader",
    "paradox.batch_duplicate_targets": (
        "Несколько операций используют один файл {target} ({first} и {second}). "
        "Используйте уникальную маску имени."
    ),
}


def _target_name(mask: str, source: Path, mode: str) -> str:
    try:
        rendered = mask.format(source_name=source.stem, mode=mode)
    except (KeyError, ValueError) as exc:
        raise ValueError(
            "Маска имени поддерживает только {source_name} и {mode}"
        ) from exc
    candidate = Path(rendered)
    if candidate.name != rendered or rendered in {"", ".", ".."}:
        raise ValueError("Маска результата не должна содержать путь")
    if candidate.suffix.casefold() != ".las":
        rendered += ".las"
    return rendered


def _write_log(result: BatchItemResult, parameters: dict[str, str], target: Path) -> None:
    payload = {
        "source": str(result.source),
        "target": str(result.target) if result.target else None,
        "status": result.status.value,
        "message": result.message,
        "records": result.records,
        "channels": result.channels,
        "warnings": result.warnings,
        "metadata": parameters,
    }
    target.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
