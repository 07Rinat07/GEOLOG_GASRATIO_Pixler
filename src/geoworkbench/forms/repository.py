from __future__ import annotations

import json
import os
from pathlib import Path
import tempfile

from geoworkbench.forms.codec import FormFormatError, form_from_dict, form_to_dict
from geoworkbench.forms.models import FormAxisKind, FormDocument, FormTemplateOrigin
from geoworkbench.forms.naming import polished_ready_form_name


class FormRepository:
    """Persistent library of ready and editable forms.

    Editable forms are stored in ``depth`` and ``time``.  Confirmed local forms
    from older GEOLOG builds are upgraded once into ``ready`` as protected
    templates.  Legacy JSON files in the repository root remain readable and are
    moved into the correct directory during the same atomic upgrade.
    """

    DEPTH_FOLDER = "depth"
    TIME_FOLDER = "time"
    READY_FOLDER = "ready"

    def __init__(self, root: Path) -> None:
        self._root = root
        self._load_errors: list[tuple[Path, str]] = []
        self._upgrade_completed = False
        self._upgraded_ready_names: tuple[str, ...] = ()

    @property
    def root(self) -> Path:
        return self._root

    @property
    def load_errors(self) -> tuple[tuple[Path, str], ...]:
        return tuple(self._load_errors)

    @property
    def upgraded_ready_names(self) -> tuple[str, ...]:
        """Names promoted during the current process startup."""

        return self._upgraded_ready_names

    def folder_for_axis(self, axis_kind: FormAxisKind) -> Path:
        folder = self.DEPTH_FOLDER if axis_kind is FormAxisKind.DEPTH else self.TIME_FOLDER
        return self._root / folder

    def save(self, form: FormDocument) -> Path:
        if form.read_only:
            raise PermissionError("Готовую или заводскую форму нельзя перезаписывать")
        target = self.folder_for_axis(form.axis_kind) / f"{form.form_id}.json"
        self._write_form(form, target)
        self._remove_other_copies(form.form_id, keep=target)
        return target

    def load(self, form_id: str) -> FormDocument:
        self._ensure_upgraded()
        target = self._find_path(form_id)
        if target is None:
            raise FileNotFoundError(form_id)
        with target.open("r", encoding="utf-8") as stream:
            return form_from_dict(json.load(stream))

    def delete(self, form_id: str) -> None:
        self._ensure_upgraded()
        target = self._find_path(form_id)
        if target is None:
            raise FileNotFoundError(form_id)
        with target.open("r", encoding="utf-8") as stream:
            form = form_from_dict(json.load(stream))
        if form.read_only:
            raise PermissionError("Готовую или заводскую форму нельзя удалить")
        target.unlink(missing_ok=False)

    def list_forms(self) -> list[FormDocument]:
        self._ensure_upgraded()
        self._load_errors = []
        if not self._root.exists():
            return []
        forms: list[FormDocument] = []
        seen_ids: set[str] = set()
        for path in self._json_paths():
            if not path.exists():
                continue
            try:
                with path.open("r", encoding="utf-8") as stream:
                    form = form_from_dict(json.load(stream))
                if form.form_id in seen_ids:
                    continue
                seen_ids.add(form.form_id)
                forms.append(form)
            except (OSError, json.JSONDecodeError, FormFormatError) as exc:
                self._load_errors.append((path, str(exc)))
        return forms

    def upgrade_legacy_forms(self) -> tuple[str, ...]:
        """Persist schema/width migrations and promote four confirmed forms.

        The operation is safe to call repeatedly.  It rewrites a file only when
        its normalized payload or destination changed, and all writes use an
        atomic temporary-file replacement.
        """

        if self._upgrade_completed:
            return self._upgraded_ready_names
        self._upgrade_completed = True
        if not self._root.exists():
            self._upgraded_ready_names = ()
            return ()

        promoted: list[str] = []
        errors: list[tuple[Path, str]] = []
        for path in self._json_paths():
            if not path.exists():
                continue
            try:
                with path.open("r", encoding="utf-8") as stream:
                    raw = json.load(stream)
                form = form_from_dict(raw)
                polished_name = polished_ready_form_name(form.name)
                promoted_now = polished_name is not None
                changed_identity = False
                if polished_name is not None and form.name != polished_name:
                    form.name = polished_name
                    changed_identity = True
                if promoted_now and not form.read_only:
                    form.read_only = True
                    changed_identity = True
                if promoted_now and form.origin is not FormTemplateOrigin.FACTORY:
                    form.origin = FormTemplateOrigin.FACTORY
                    changed_identity = True
                if promoted_now and not form.description.strip():
                    form.description = (
                        "Готовая пользовательская форма, перенесённая из локальной "
                        "библиотеки GEOLOG и защищённая от случайного изменения."
                    )
                    changed_identity = True
                if changed_identity:
                    form.revision = max(1, form.revision + 1)
                    form.validate()

                target = (
                    self._root / self.READY_FOLDER / f"{form.form_id}.json"
                    if form.read_only and form.origin is FormTemplateOrigin.FACTORY
                    else self.folder_for_axis(form.axis_kind) / f"{form.form_id}.json"
                )
                encoded = form_to_dict(form)
                normalized_raw = json.dumps(raw, ensure_ascii=False, sort_keys=True)
                normalized_encoded = json.dumps(encoded, ensure_ascii=False, sort_keys=True)
                if target != path or normalized_raw != normalized_encoded:
                    self._write_payload(encoded, target)
                    self._remove_other_copies(form.form_id, keep=target)
                    if path != target:
                        path.unlink(missing_ok=True)
                if promoted_now:
                    promoted.append(form.name)
            except (OSError, json.JSONDecodeError, FormFormatError, ValueError) as exc:
                errors.append((path, str(exc)))

        self._load_errors = errors
        self._upgraded_ready_names = tuple(sorted(set(promoted), key=str.casefold))
        return self._upgraded_ready_names

    def _ensure_upgraded(self) -> None:
        if not self._upgrade_completed:
            self.upgrade_legacy_forms()

    def _json_paths(self) -> list[Path]:
        if not self._root.exists():
            return []
        return sorted(
            self._root.rglob("*.json"),
            key=lambda path: (len(path.relative_to(self._root).parts), str(path).casefold()),
        )

    def _find_path(self, form_id: str) -> Path | None:
        candidates = (
            self._root / self.READY_FOLDER / f"{form_id}.json",
            self._root / self.DEPTH_FOLDER / f"{form_id}.json",
            self._root / self.TIME_FOLDER / f"{form_id}.json",
            self._root / f"{form_id}.json",
        )
        return next((path for path in candidates if path.exists()), None)

    def _write_form(self, form: FormDocument, target: Path) -> None:
        self._write_payload(form_to_dict(form), target)

    @staticmethod
    def _write_payload(payload: dict[str, object], target: Path) -> None:
        target.parent.mkdir(parents=True, exist_ok=True)
        text = json.dumps(payload, ensure_ascii=False, indent=2)
        fd, temp_name = tempfile.mkstemp(
            prefix=f".{target.name}.", suffix=".tmp", dir=target.parent
        )
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as stream:
                stream.write(text)
                stream.flush()
                os.fsync(stream.fileno())
            os.replace(temp_name, target)
        except Exception:
            Path(temp_name).unlink(missing_ok=True)
            raise

    def _remove_other_copies(self, form_id: str, *, keep: Path) -> None:
        for candidate in (
            self._root / self.READY_FOLDER / f"{form_id}.json",
            self._root / self.DEPTH_FOLDER / f"{form_id}.json",
            self._root / self.TIME_FOLDER / f"{form_id}.json",
            self._root / f"{form_id}.json",
        ):
            if candidate != keep:
                candidate.unlink(missing_ok=True)
