from __future__ import annotations

from dataclasses import dataclass, replace
from enum import StrEnum
import json
import os
from pathlib import Path
import tempfile
from typing import Callable, Iterable

import numpy as np

from geoworkbench.domain.models import Dataset
from geoworkbench.services.depth_axis import (
    analyze_depth_axis,
    analyze_depth_resample,
    create_resampled_depth_copy,
)

from .analysis import analyze_table
from .importer import default_mappings, import_paradox
from .models import DatasetClassification, IssueSeverity, ParadoxImportPlan, ParadoxTable
from .reader import read_paradox


class BatchStatus(StrEnum):
    SUCCESS = "success"
    WARNING = "warning"
    ERROR = "error"
    SKIPPED = "skipped"
    CONFIGURATION_REQUIRED = "configuration_required"


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
    target_depth_step: float | None = None,
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
        stage_key = "paradox.batch_stage_read"
        try:
            table = read_paradox(source, cancelled=cancelled)
            stage_key = "paradox.batch_stage_analysis"
            quality = analyze_table(table)
            material_issues = [
                issue
                for issue in quality.issues
                if issue.severity
                in {IssueSeverity.WARNING, IssueSeverity.ERROR, IssueSeverity.CRITICAL}
            ]
            stage_key = "paradox.batch_stage_plan"
            plan = plan_factory(source, table) if plan_factory is not None else None
            if plan is None:
                if quality.classification in {
                    DatasetClassification.MIXED,
                    DatasetClassification.UNDEFINED,
                }:
                    results.append(
                        BatchItemResult(
                            source,
                            target,
                            BatchStatus.CONFIGURATION_REQUIRED,
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
            if mode == "depth" and target_depth_step is not None:
                plan = replace(
                    plan,
                    sort_by_index=True,
                    duplicate_depth_policy="last",
                )
            if mode == "depth" and plan.depth_field is None:
                raise ValueError(message("paradox.batch_profile_no_depth"))
            if mode == "time" and plan.time_field is None:
                raise ValueError(message("paradox.batch_profile_no_time"))
            stage_key = "paradox.batch_stage_import"
            imported = import_paradox(
                source,
                plan,
                table=table,
                quality=quality,
                cancelled=cancelled,
            )
            export_dataset = imported.dataset
            if mode == "depth" and target_depth_step is not None:
                export_dataset = _resample_depth_for_batch(
                    imported.dataset,
                    target_depth_step,
                )
            from geoworkbench.data.las_adapter import export_las, import_las
            from geoworkbench.data.las_export_plan import LasExportPlan

            export_plan = LasExportPlan(null_value=plan.null_value)
            temporary_target = _temporary_las_target(target)
            stage_key = "paradox.batch_stage_export"
            try:
                export_las(
                    export_dataset,
                    temporary_target,
                    overwrite=True,
                    plan=export_plan,
                )
                # The final path is replaced only after the application has reopened
                # the complete temporary LAS and verified the actual source grid.
                stage_key = "paradox.batch_stage_roundtrip"
                reopened = import_las(temporary_target)
                actual_step = _validate_roundtrip(
                    export_dataset,
                    reopened,
                    precision=export_plan.precision,
                    message=message,
                )
                stage_key = "paradox.batch_stage_commit"
                os.replace(temporary_target, target)
            finally:
                temporary_target.unlink(missing_ok=True)
            status = BatchStatus.WARNING if material_issues else BatchStatus.SUCCESS
            result = BatchItemResult(
                source,
                target,
                status,
                message("paradox.batch_roundtrip_success", step=f"{actual_step:g}"),
                records=table.rows_read,
                channels=imported.imported_channels,
                warnings=len(material_issues),
            )
            _write_log(result, export_dataset.parameters, target.with_suffix(".import.json"))
            results.append(result)
        except Exception as exc:
            results.append(
                BatchItemResult(
                    source,
                    target,
                    BatchStatus.ERROR,
                    message(
                        "paradox.batch_stage_failed",
                        stage=message(stage_key),
                        error=str(exc),
                    ),
                )
            )
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
    "paradox.batch_roundtrip_success": (
        "LAS создан, проверен и сохраняет фактический STEP={step}"
    ),
    "paradox.batch_stage_read": "чтение DB",
    "paradox.batch_stage_analysis": "анализ каналов",
    "paradox.batch_stage_plan": "подготовка плана импорта",
    "paradox.batch_stage_import": "создание набора данных",
    "paradox.batch_stage_export": "запись LAS",
    "paradox.batch_stage_roundtrip": "повторное открытие LAS",
    "paradox.batch_stage_commit": "сохранение проверенного LAS",
    "paradox.batch_stage_failed": "Этап «{stage}»: {error}",
    "paradox.batch_roundtrip_rows": (
        "После повторного открытия число строк изменилось: ожидалось {expected}, получено {actual}"
    ),
    "paradox.batch_roundtrip_index": (
        "После повторного открытия значения индексной колонки отличаются от источника"
    ),
    "paradox.batch_roundtrip_header": (
        "Заголовок {name} не соответствует фактической сетке: ожидалось {expected}, "
        "получено {actual}"
    ),
    "paradox.batch_roundtrip_curves": (
        "После повторного открытия изменился набор каналов: {details}"
    ),
    "paradox.batch_roundtrip_curve_values": (
        "После повторного открытия изменились значения канала {mnemonic}"
    ),
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


def _temporary_las_target(target: Path) -> Path:
    target.parent.mkdir(parents=True, exist_ok=True)
    descriptor, name = tempfile.mkstemp(
        prefix=f".{target.stem}.",
        suffix=".pending.las",
        dir=target.parent,
    )
    os.close(descriptor)
    return Path(name)


def _validate_roundtrip(
    expected: Dataset,
    actual: Dataset,
    *,
    precision: int,
    message: Callable[..., str],
) -> float:
    expected_index = np.asarray(expected.active_index.values, dtype=np.float64)
    actual_index = np.asarray(actual.active_index.values, dtype=np.float64)
    if expected_index.shape != actual_index.shape:
        raise RuntimeError(
            message(
                "paradox.batch_roundtrip_rows",
                expected=expected_index.size,
                actual=actual_index.size,
            )
        )
    tolerance = 10.0 ** (-precision)
    if not np.allclose(
        expected_index,
        actual_index,
        rtol=0.0,
        atol=tolerance,
        equal_nan=True,
    ):
        raise RuntimeError(message("paradox.batch_roundtrip_index"))

    expected_headers = {
        "STRT": float(expected_index[0]),
        "STOP": float(expected_index[-1]),
        "STEP": _signed_nominal_step(expected_index),
    }
    for name, expected_value in expected_headers.items():
        try:
            actual_value = float(actual.headers[name])
        except (KeyError, TypeError, ValueError) as exc:
            raise RuntimeError(
                message(
                    "paradox.batch_roundtrip_header",
                    name=name,
                    expected=f"{expected_value:g}",
                    actual="—",
                )
            ) from exc
        if not np.isclose(expected_value, actual_value, rtol=0.0, atol=tolerance):
            raise RuntimeError(
                message(
                    "paradox.batch_roundtrip_header",
                    name=name,
                    expected=f"{expected_value:g}",
                    actual=f"{actual_value:g}",
                )
            )

    expected_curves = {
        curve.metadata.original_mnemonic.casefold(): curve
        for curve in expected.curves.values()
    }
    actual_curves = {
        curve.metadata.original_mnemonic.casefold(): curve
        for curve in actual.curves.values()
    }
    if expected_curves.keys() != actual_curves.keys():
        missing = sorted(expected_curves.keys() - actual_curves.keys())
        extra = sorted(actual_curves.keys() - expected_curves.keys())
        details = f"missing={missing or '—'}; extra={extra or '—'}"
        raise RuntimeError(
            message("paradox.batch_roundtrip_curves", details=details)
        )
    for key, expected_curve in expected_curves.items():
        actual_curve = actual_curves[key]
        if not np.allclose(
            np.asarray(expected_curve.values, dtype=np.float64),
            np.asarray(actual_curve.values, dtype=np.float64),
            rtol=0.0,
            atol=tolerance,
            equal_nan=True,
        ):
            raise RuntimeError(
                message(
                    "paradox.batch_roundtrip_curve_values",
                    mnemonic=expected_curve.metadata.original_mnemonic,
                )
            )
    return expected_headers["STEP"]


def _signed_nominal_step(values: np.ndarray) -> float:
    finite = np.asarray(values, dtype=np.float64)
    finite = finite[np.isfinite(finite)]
    differences = np.diff(finite)
    positive = differences[differences > 0]
    if positive.size:
        return float(np.median(positive))
    negative = differences[differences < 0]
    return float(np.median(negative)) if negative.size else 0.0


def _resample_depth_for_batch(dataset: Dataset, step: float) -> Dataset:
    if not np.isfinite(step) or step <= 0:
        raise ValueError("Целевой шаг глубины должен быть конечным положительным числом")
    report = analyze_depth_axis(dataset.depth)
    if report.start is None or report.stop is None:
        raise ValueError("Невозможно определить диапазон глубины для ресэмплинга")
    plan = analyze_depth_resample(dataset, report.start, report.stop, step)
    result = create_resampled_depth_copy(
        dataset,
        plan,
        name=f"{dataset.name} — derived {step:g} m",
    )
    result.parameters.update(
        {
            "PARADOX_BATCH_SOURCE_DEPTH_STEP_M": (
                f"{report.nominal_step:g}" if report.nominal_step is not None else ""
            ),
            "PARADOX_BATCH_TARGET_DEPTH_STEP_M": f"{step:g}",
            "PARADOX_BATCH_RESAMPLE_METHOD": "linear-without-bridging",
            "PARADOX_BATCH_RESAMPLE_DUPLICATE_POLICY": "last",
        }
    )
    return result


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
