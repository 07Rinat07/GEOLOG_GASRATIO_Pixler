from __future__ import annotations

import json
import os
import shutil
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Iterable, Sequence

from geoworkbench.services.report_passport import (
    ReportPassport,
    finalize_report_passport,
    load_report_passport,
    passport_sidecar_path,
    verify_report_output_artifacts,
    write_report_passport,
)

REPORT_OUTPUT_TRANSACTION_SCHEMA_VERSION = 1
REPORT_OUTPUT_TRANSACTION_SUFFIX = ".report-transaction.json"


class ReportOutputTransactionError(RuntimeError):
    pass


class ReportOutputRecoveryError(ReportOutputTransactionError):
    pass


@dataclass(frozen=True, slots=True)
class ReportOutputTransactionResult:
    output_paths: tuple[Path, ...]
    passport_path: Path
    passport: ReportPassport

    @property
    def primary_path(self) -> Path:
        return self.output_paths[0]


@dataclass(frozen=True, slots=True)
class _Operation:
    destination: Path
    staged: Path | None
    backup: Path
    existed: bool

    def payload(self) -> dict[str, object]:
        return {
            "destination": str(self.destination),
            "staged": str(self.staged) if self.staged is not None else None,
            "backup": str(self.backup),
            "existed": self.existed,
        }


def report_transaction_journal_path(output: str | Path) -> Path:
    target = Path(output)
    return target.with_name(f".{target.name}{REPORT_OUTPUT_TRANSACTION_SUFFIX}")


def execute_report_output_transaction(
    output: str | Path,
    producer: Callable[[Path], Path | Sequence[Path]],
    passport: ReportPassport,
    *,
    overwrite: bool = False,
) -> ReportOutputTransactionResult:
    """Render output and passport as one recoverable filesystem transaction.

    The producer writes only inside a staging directory. The transaction fingerprints the
    completed staged bytes, signs the final passport, journals backups and replacements, then
    verifies the installed files before declaring the transaction committed.
    """

    target = Path(output)
    target.parent.mkdir(parents=True, exist_ok=True)
    recover_report_output_transaction(target)
    sidecar = passport_sidecar_path(target)
    if not overwrite:
        for existing in (target, sidecar):
            if existing.exists():
                raise FileExistsError(existing)

    workspace = Path(
        tempfile.mkdtemp(prefix=f".{target.name}.report-txn-", dir=target.parent)
    )
    journal = report_transaction_journal_path(target)
    try:
        _write_journal(journal, target, workspace, "rendering", ())
    except Exception:
        shutil.rmtree(workspace, ignore_errors=True)
        raise
    staged_target = workspace / target.name

    try:
        produced_value = producer(staged_target)
        staged_outputs = _normalize_staged_outputs(produced_value, workspace)
        final_outputs = tuple(target.parent / path.relative_to(workspace) for path in staged_outputs)
        if len(set(final_outputs)) != len(final_outputs):
            raise ReportOutputTransactionError("Транзакция содержит повторяющиеся output-файлы")
        if not overwrite:
            for destination in final_outputs:
                if destination.exists():
                    raise FileExistsError(destination)

        finalized_passport = finalize_report_passport(
            passport,
            staged_outputs,
            artifact_names=tuple(path.name for path in final_outputs),
        )
        staged_sidecar = write_report_passport(
            finalized_passport,
            staged_target,
            overwrite=False,
        )

        obsolete = _obsolete_output_paths(target, final_outputs, sidecar) if overwrite else ()
        destinations: list[tuple[Path, Path | None]] = list(zip(final_outputs, staged_outputs, strict=True))
        destinations.append((sidecar, staged_sidecar))
        destinations.extend((path, None) for path in obsolete)
        operations = _build_operations(workspace, destinations)
        _write_journal(journal, target, workspace, "prepared", operations)

        for operation in operations:
            if operation.existed:
                operation.backup.parent.mkdir(parents=True, exist_ok=True)
                _replace_file(operation.destination, operation.backup)
        _sync_directory(target.parent)
        _write_journal(journal, target, workspace, "backed-up", operations)

        for operation in operations:
            if operation.staged is not None:
                operation.destination.parent.mkdir(parents=True, exist_ok=True)
                _install_operation(operation)
        _sync_directory(target.parent)
        _verify_installed_outputs(finalized_passport, final_outputs, sidecar)
        _write_journal(journal, target, workspace, "committed", operations)
        _cleanup_committed_transaction(journal, workspace, operations)
        return ReportOutputTransactionResult(
            output_paths=final_outputs,
            passport_path=sidecar,
            passport=finalized_passport,
        )
    except Exception:
        try:
            _recover_from_journal(journal)
        except ReportOutputRecoveryError:
            raise
        raise


def recover_report_output_transaction(output: str | Path) -> bool:
    """Recover one interrupted report transaction associated with *output*.

    Returns ``True`` when a journal was found and recovered or cleaned up.
    """

    journal = report_transaction_journal_path(output)
    if not journal.exists():
        return False
    _recover_from_journal(journal)
    return True


def recover_report_output_transactions(directory: str | Path) -> tuple[Path, ...]:
    root = Path(directory)
    recovered: list[Path] = []
    if not root.exists():
        return ()
    pattern = f".*{REPORT_OUTPUT_TRANSACTION_SUFFIX}"
    for journal in sorted(root.glob(pattern)):
        _recover_from_journal(journal)
        recovered.append(journal)
    return tuple(recovered)


def _normalize_staged_outputs(
    value: Path | Sequence[Path], workspace: Path
) -> tuple[Path, ...]:
    raw = (value,) if isinstance(value, Path) else tuple(value)
    if not raw:
        raise ReportOutputTransactionError("Producer не создал ни одного output-файла")
    resolved_workspace = workspace.resolve()
    outputs: list[Path] = []
    for item in raw:
        path = Path(item)
        try:
            path.resolve().relative_to(resolved_workspace)
        except ValueError as exc:
            raise ReportOutputTransactionError(
                "Producer попытался записать output за пределами staging-каталога"
            ) from exc
        if path.resolve().parent != resolved_workspace:
            raise ReportOutputTransactionError(
                "Producer должен создавать output-файлы в корне staging-каталога"
            )
        if not path.is_file() or path.stat().st_size <= 0:
            raise ReportOutputTransactionError(f"Output-файл не создан или пуст: {path.name}")
        outputs.append(path)
    return tuple(outputs)


def _build_operations(
    workspace: Path,
    destinations: Sequence[tuple[Path, Path | None]],
) -> tuple[_Operation, ...]:
    backup_root = workspace / "backups"
    operations: list[_Operation] = []
    seen: set[Path] = set()
    for index, (destination, staged) in enumerate(destinations, start=1):
        destination = destination.resolve()
        if destination in seen:
            continue
        seen.add(destination)
        backup = backup_root / f"{index:04d}-{destination.name}"
        operations.append(
            _Operation(
                destination=destination,
                staged=staged.resolve() if staged is not None else None,
                backup=backup.resolve(),
                existed=destination.exists(),
            )
        )
    return tuple(operations)


def _obsolete_output_paths(
    target: Path,
    final_outputs: Sequence[Path],
    sidecar: Path,
) -> tuple[Path, ...]:
    keep = {path.resolve() for path in final_outputs}
    obsolete: set[Path] = set()
    if sidecar.exists():
        try:
            payload = json.loads(sidecar.read_text(encoding="utf-8"))
        except (OSError, UnicodeError, json.JSONDecodeError):
            payload = {}
        artifacts = payload.get("artifacts") if isinstance(payload, dict) else None
        if isinstance(artifacts, list):
            for item in artifacts:
                if not isinstance(item, dict):
                    continue
                name = item.get("file_name")
                if isinstance(name, str) and name == Path(name).name:
                    candidate = target.parent / name
                    if candidate.resolve() not in keep and candidate.exists():
                        obsolete.add(candidate)
    legacy_pattern = f"{target.stem}_page_[0-9][0-9][0-9]{target.suffix}"
    for candidate in target.parent.glob(legacy_pattern):
        if candidate.resolve() not in keep:
            obsolete.add(candidate)
    if target.resolve() not in keep and target.exists():
        obsolete.add(target)
    return tuple(sorted(obsolete))


def _write_journal(
    journal: Path,
    target: Path,
    workspace: Path,
    stage: str,
    operations: Iterable[_Operation],
) -> None:
    payload = {
        "schema_version": REPORT_OUTPUT_TRANSACTION_SCHEMA_VERSION,
        "primary_output": str(target.resolve()),
        "workspace": str(workspace.resolve()),
        "stage": stage,
        "operations": [operation.payload() for operation in operations],
    }
    temporary = journal.with_name(journal.name + ".tmp")
    try:
        with temporary.open("w", encoding="utf-8", newline="\n") as stream:
            json.dump(payload, stream, ensure_ascii=False, indent=2, sort_keys=True)
            stream.write("\n")
            stream.flush()
            os.fsync(stream.fileno())
        _replace_file(temporary, journal)
        _sync_directory(journal.parent)
    except Exception as exc:
        temporary.unlink(missing_ok=True)
        raise ReportOutputTransactionError(
            f"Не удалось записать журнал report-транзакции: {journal}"
        ) from exc


def _read_journal(journal: Path) -> tuple[str, Path, tuple[_Operation, ...]]:
    try:
        payload = json.loads(journal.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise ReportOutputRecoveryError(
            f"Не удалось прочитать журнал report-транзакции: {journal}"
        ) from exc
    if not isinstance(payload, dict) or payload.get("schema_version") != REPORT_OUTPUT_TRANSACTION_SCHEMA_VERSION:
        raise ReportOutputRecoveryError("Неподдерживаемый журнал report-транзакции")
    stage = payload.get("stage")
    workspace_value = payload.get("workspace")
    operation_values = payload.get("operations")
    if not isinstance(stage, str) or not isinstance(workspace_value, str) or not isinstance(operation_values, list):
        raise ReportOutputRecoveryError("Журнал report-транзакции имеет неверную структуру")
    workspace = Path(workspace_value)
    operations: list[_Operation] = []
    for item in operation_values:
        if not isinstance(item, dict):
            raise ReportOutputRecoveryError("Журнал содержит повреждённую файловую операцию")
        destination = item.get("destination")
        backup = item.get("backup")
        staged = item.get("staged")
        existed = item.get("existed")
        if not isinstance(destination, str) or not isinstance(backup, str) or not isinstance(existed, bool):
            raise ReportOutputRecoveryError("Журнал содержит неполную файловую операцию")
        if staged is not None and not isinstance(staged, str):
            raise ReportOutputRecoveryError("Журнал содержит неверный staged path")
        operations.append(
            _Operation(
                destination=Path(destination),
                staged=Path(staged) if staged is not None else None,
                backup=Path(backup),
                existed=existed,
            )
        )
    result = tuple(operations)
    _validate_recovery_paths(journal, workspace, result)
    return stage, workspace, result


def _validate_recovery_paths(
    journal: Path, workspace: Path, operations: Sequence[_Operation]
) -> None:
    root = journal.parent.resolve()
    resolved_workspace = workspace.resolve()
    if resolved_workspace.parent != root or not resolved_workspace.name.startswith("."):
        raise ReportOutputRecoveryError("Журнал содержит небезопасный workspace path")
    for operation in operations:
        destination = operation.destination.resolve()
        if destination.parent != root:
            raise ReportOutputRecoveryError("Журнал содержит output за пределами каталога")
        for internal in (operation.staged, operation.backup):
            if internal is None:
                continue
            try:
                internal.resolve().relative_to(resolved_workspace)
            except ValueError as exc:
                raise ReportOutputRecoveryError(
                    "Журнал содержит внутренний path за пределами workspace"
                ) from exc


def _recover_from_journal(journal: Path) -> None:
    if not journal.exists():
        return
    stage, workspace, operations = _read_journal(journal)
    try:
        if stage == "committed" and all(
            (operation.destination.exists() if operation.staged is not None else not operation.destination.exists())
            for operation in operations
        ):
            _cleanup_committed_transaction(journal, workspace, operations)
            return
        for operation in reversed(operations):
            if operation.backup.exists():
                if operation.destination.exists():
                    operation.destination.unlink()
                operation.destination.parent.mkdir(parents=True, exist_ok=True)
                _replace_file(operation.backup, operation.destination)
            elif not operation.existed and operation.destination.exists():
                operation.destination.unlink()
        _sync_directory(journal.parent)
        shutil.rmtree(workspace, ignore_errors=False) if workspace.exists() else None
        journal.unlink(missing_ok=True)
        _sync_directory(journal.parent)
    except Exception as exc:
        raise ReportOutputRecoveryError(
            f"Не удалось восстановить report-транзакцию: {journal}"
        ) from exc


def _cleanup_committed_transaction(
    journal: Path,
    workspace: Path,
    operations: Sequence[_Operation],
) -> None:
    for operation in operations:
        operation.backup.unlink(missing_ok=True)
    if workspace.exists():
        shutil.rmtree(workspace)
    journal.unlink(missing_ok=True)
    _sync_directory(journal.parent)


def _verify_installed_outputs(
    passport: ReportPassport,
    output_paths: Sequence[Path],
    sidecar: Path,
) -> None:
    if not sidecar.exists():
        raise ReportOutputTransactionError("Passport sidecar не установлен")
    loaded = load_report_passport(sidecar)
    if loaded.get("passport_sha256") != passport.passport_sha256:
        raise ReportOutputTransactionError("Установлен неверный Report Passport")
    verify_report_output_artifacts(passport.payload(), sidecar.parent)
    expected = {item.file_name for item in passport.artifacts}
    actual = {path.name for path in output_paths}
    if expected != actual:
        raise ReportOutputTransactionError("Установленные output-файлы не совпадают с паспортом")


def _install_operation(operation: _Operation) -> None:
    assert operation.staged is not None
    _replace_file(operation.staged, operation.destination)


def _replace_file(source: Path, destination: Path) -> None:
    os.replace(source, destination)


def _sync_directory(directory: Path) -> None:
    if os.name == "nt":
        return
    try:
        descriptor = os.open(directory, os.O_RDONLY)
    except OSError:
        return
    try:
        os.fsync(descriptor)
    except OSError:
        pass
    finally:
        os.close(descriptor)
