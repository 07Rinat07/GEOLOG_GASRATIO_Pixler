from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
import faulthandler
import json
import logging
from logging.handlers import RotatingFileHandler
import os
from pathlib import Path
import platform
import shutil
import sys
import threading
from types import TracebackType
from typing import Any, Callable
from zipfile import ZIP_DEFLATED, ZipFile


_LOGGER_NAME = "geoworkbench"
_CURRENT: "ApplicationLogManager | None" = None
_PREVIOUS_SYS_EXCEPTOOK: Callable[..., Any] | None = None
_PREVIOUS_THREAD_EXCEPTOOK: Callable[..., Any] | None = None


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _safe_value(value: object) -> str:
    text = str(value).replace("\r", "\\r").replace("\n", "\\n")
    return text if len(text) <= 600 else text[:597] + "..."


def _context_text(context: dict[str, object]) -> str:
    if not context:
        return ""
    return " | " + " ".join(
        f"{key}={json.dumps(_safe_value(value), ensure_ascii=False)}"
        for key, value in sorted(context.items())
        if value is not None
    )


@dataclass(frozen=True, slots=True)
class DiagnosticBundleResult:
    path: Path
    included_files: tuple[str, ...]


class ApplicationLogManager:
    """Persistent rotating diagnostics for application, Qt and support events.

    The manager intentionally writes human-readable UTF-8 logs rather than a
    database.  A user can attach the current log or a generated diagnostics ZIP
    without exposing project datasets, LAS values or saved forms.
    """

    def __init__(
        self,
        log_directory: str | Path,
        *,
        application_version: str,
        max_bytes: int = 5 * 1024 * 1024,
        backup_count: int = 5,
    ) -> None:
        self.log_directory = Path(log_directory).expanduser().resolve()
        self.log_directory.mkdir(parents=True, exist_ok=True)
        self.application_version = str(application_version)
        self.current_log_path = self.log_directory / "geolog.log"
        self.crash_log_path = self.log_directory / "geolog-crash.log"
        self._closed = False
        self._logger = logging.getLogger(_LOGGER_NAME)
        self._logger.setLevel(logging.DEBUG)
        self._logger.propagate = False
        self._logger.handlers.clear()

        handler = RotatingFileHandler(
            self.current_log_path,
            maxBytes=max(1024, int(max_bytes)),
            backupCount=max(1, int(backup_count)),
            encoding="utf-8",
            delay=False,
        )
        handler.setLevel(logging.DEBUG)
        handler.setFormatter(
            logging.Formatter(
                "%(asctime)s.%(msecs)03dZ | %(levelname)s | %(threadName)s | "
                "%(name)s | %(message)s",
                datefmt="%Y-%m-%dT%H:%M:%S",
            )
        )
        self._logger.addHandler(handler)
        self._handler = handler
        self._crash_handle = self.crash_log_path.open("a", encoding="utf-8", buffering=1)
        try:
            faulthandler.enable(file=self._crash_handle, all_threads=True)
        except (RuntimeError, OSError):
            pass
        logging.captureWarnings(True)
        self.event(
            "application.logging.started",
            version=self.application_version,
            python=sys.version.split()[0],
            platform=platform.platform(),
            pid=os.getpid(),
            log_file=self.current_log_path,
        )

    @property
    def logger(self) -> logging.Logger:
        return self._logger

    def event(self, event: str, *, level: int = logging.INFO, **context: object) -> None:
        self._logger.log(level, "event=%s%s", event, _context_text(context))

    def warning(self, event: str, **context: object) -> None:
        self.event(event, level=logging.WARNING, **context)

    def error(self, event: str, **context: object) -> None:
        self.event(event, level=logging.ERROR, **context)

    def exception(
        self,
        event: str,
        exc: BaseException,
        *,
        context: dict[str, object] | None = None,
    ) -> None:
        self._logger.error(
            "event=%s%s",
            event,
            _context_text(
                {
                    **(context or {}),
                    "exception_type": type(exc).__name__,
                    "exception": str(exc),
                }
            ),
            exc_info=(type(exc), exc, exc.__traceback__),
        )

    def flush(self) -> None:
        for handler in tuple(self._logger.handlers):
            try:
                handler.flush()
            except Exception:
                pass
        try:
            self._crash_handle.flush()
        except Exception:
            pass

    def close(self) -> None:
        if self._closed:
            return
        self._closed = True
        self.event("application.logging.stopped")
        self.flush()
        try:
            faulthandler.disable()
        except RuntimeError:
            pass
        for handler in tuple(self._logger.handlers):
            try:
                handler.close()
            finally:
                self._logger.removeHandler(handler)
        try:
            self._crash_handle.close()
        except Exception:
            pass

    def recent_log_files(self) -> tuple[Path, ...]:
        candidates = [
            path
            for path in self.log_directory.glob("geolog*.log*")
            if path.is_file() and path.stat().st_size > 0
        ]
        return tuple(sorted(candidates, key=lambda item: item.stat().st_mtime, reverse=True))

    def build_diagnostic_bundle(
        self,
        destination: str | Path,
        *,
        runtime_context: dict[str, object] | None = None,
        extra_files: tuple[Path, ...] = (),
    ) -> DiagnosticBundleResult:
        """Create a support ZIP without copying project datasets or LAS content."""

        self.flush()
        target = Path(destination).expanduser().resolve()
        target.parent.mkdir(parents=True, exist_ok=True)
        temporary = target.with_name(target.name + ".tmp")
        if temporary.exists():
            temporary.unlink()
        included: list[str] = []
        report = {
            "created_at_utc": _utc_now().isoformat(),
            "application_version": self.application_version,
            "python": sys.version,
            "platform": platform.platform(),
            "architecture": platform.machine(),
            "processor": platform.processor(),
            "pid": os.getpid(),
            "log_directory": str(self.log_directory),
            "runtime_context": runtime_context or {},
        }
        with ZipFile(temporary, "w", compression=ZIP_DEFLATED) as archive:
            archive.writestr(
                "system-report.json",
                json.dumps(report, ensure_ascii=False, indent=2, default=str) + "\n",
            )
            included.append("system-report.json")
            for source in self.recent_log_files():
                arcname = f"logs/{source.name}"
                archive.write(source, arcname)
                included.append(arcname)
            for source in extra_files:
                source = Path(source)
                if not source.is_file():
                    continue
                arcname = f"attachments/{source.name}"
                archive.write(source, arcname)
                included.append(arcname)
            archive.writestr(
                "README.txt",
                "GEOLOG GASRATIO@Pixler diagnostics bundle.\n"
                "It contains runtime logs and system metadata only.\n"
                "Project datasets, LAS values, forms and user files are not included.\n",
            )
            included.append("README.txt")
        os.replace(temporary, target)
        self.event(
            "diagnostics.bundle.created",
            destination=target,
            files=len(included),
        )
        return DiagnosticBundleResult(target, tuple(included))


def configure_application_logging(
    log_directory: str | Path,
    *,
    application_version: str,
) -> ApplicationLogManager:
    global _CURRENT
    if _CURRENT is not None:
        _CURRENT.close()
    _CURRENT = ApplicationLogManager(
        log_directory,
        application_version=application_version,
    )
    return _CURRENT


def current_application_log_manager() -> ApplicationLogManager | None:
    return _CURRENT


def application_logger() -> logging.Logger:
    return logging.getLogger(_LOGGER_NAME)


def log_event(event: str, **context: object) -> None:
    manager = current_application_log_manager()
    if manager is not None:
        manager.event(event, **context)
    else:
        application_logger().info("event=%s%s", event, _context_text(context))


def log_exception(
    event: str,
    exc: BaseException,
    **context: object,
) -> None:
    manager = current_application_log_manager()
    if manager is not None:
        manager.exception(event, exc, context=context)
    else:
        application_logger().exception("event=%s%s", event, _context_text(context))


def install_python_exception_hooks(manager: ApplicationLogManager) -> None:
    """Capture uncaught exceptions from the main and worker Python threads."""

    global _PREVIOUS_SYS_EXCEPTOOK, _PREVIOUS_THREAD_EXCEPTOOK
    if _PREVIOUS_SYS_EXCEPTOOK is None:
        _PREVIOUS_SYS_EXCEPTOOK = sys.excepthook
    if _PREVIOUS_THREAD_EXCEPTOOK is None:
        _PREVIOUS_THREAD_EXCEPTOOK = threading.excepthook

    def system_hook(
        exc_type: type[BaseException],
        exc: BaseException,
        traceback: TracebackType | None,
    ) -> None:
        if exc.__traceback__ is None and traceback is not None:
            exc = exc.with_traceback(traceback)
        manager.exception("python.uncaught", exc)
        manager.flush()
        previous = _PREVIOUS_SYS_EXCEPTOOK
        if previous is not None and previous is not system_hook:
            previous(exc_type, exc, traceback)

    def thread_hook(args: threading.ExceptHookArgs) -> None:
        exc = args.exc_value
        if exc.__traceback__ is None and args.exc_traceback is not None:
            exc = exc.with_traceback(args.exc_traceback)
        manager.exception(
            "python.thread.uncaught",
            exc,
            context={"thread": getattr(args.thread, "name", "unknown")},
        )
        manager.flush()
        previous = _PREVIOUS_THREAD_EXCEPTOOK
        if previous is not None and previous is not thread_hook:
            previous(args)

    sys.excepthook = system_hook
    threading.excepthook = thread_hook


def copy_log_file(source: str | Path, destination: str | Path) -> Path:
    source_path = Path(source)
    target = Path(destination)
    target.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(source_path, target)
    return target
