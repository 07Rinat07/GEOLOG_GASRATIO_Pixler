from __future__ import annotations

import json
import os
from pathlib import Path
import tempfile

from geoworkbench.forms.codec import FormFormatError, form_from_dict, form_to_dict
from geoworkbench.forms.models import FormAxisKind, FormDocument


class FormRepository:
    """Persistent library of user forms separated by vertical-axis type.

    New forms are stored in ``depth`` and ``time`` subdirectories. Legacy JSON
    files in the repository root remain readable and are moved into the correct
    directory the next time they are saved.
    """

    DEPTH_FOLDER = "depth"
    TIME_FOLDER = "time"

    def __init__(self, root: Path) -> None:
        self._root = root
        self._load_errors: list[tuple[Path, str]] = []

    @property
    def root(self) -> Path:
        return self._root

    @property
    def load_errors(self) -> tuple[tuple[Path, str], ...]:
        return tuple(self._load_errors)

    def folder_for_axis(self, axis_kind: FormAxisKind) -> Path:
        folder = self.DEPTH_FOLDER if axis_kind is FormAxisKind.DEPTH else self.TIME_FOLDER
        return self._root / folder

    def save(self, form: FormDocument) -> Path:
        if form.read_only:
            raise PermissionError("Заводскую форму нельзя сохранять как пользовательскую")
        target_dir = self.folder_for_axis(form.axis_kind)
        target_dir.mkdir(parents=True, exist_ok=True)
        target = target_dir / f"{form.form_id}.json"
        payload = json.dumps(form_to_dict(form), ensure_ascii=False, indent=2)
        fd, temp_name = tempfile.mkstemp(
            prefix=f".{target.name}.", suffix=".tmp", dir=target_dir
        )
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as stream:
                stream.write(payload)
                stream.flush()
                os.fsync(stream.fileno())
            os.replace(temp_name, target)
            self._remove_other_copies(form.form_id, keep=target)
        except Exception:
            Path(temp_name).unlink(missing_ok=True)
            raise
        return target

    def load(self, form_id: str) -> FormDocument:
        target = self._find_path(form_id)
        if target is None:
            raise FileNotFoundError(form_id)
        with target.open("r", encoding="utf-8") as stream:
            return form_from_dict(json.load(stream))

    def delete(self, form_id: str) -> None:
        target = self._find_path(form_id)
        if target is None:
            raise FileNotFoundError(form_id)
        target.unlink(missing_ok=False)

    def list_forms(self) -> list[FormDocument]:
        self._load_errors = []
        if not self._root.exists():
            return []
        forms: list[FormDocument] = []
        seen_ids: set[str] = set()
        paths = sorted(
            self._root.rglob("*.json"),
            key=lambda path: (len(path.relative_to(self._root).parts), str(path).casefold()),
        )
        for path in paths:
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

    def _find_path(self, form_id: str) -> Path | None:
        candidates = (
            self._root / self.DEPTH_FOLDER / f"{form_id}.json",
            self._root / self.TIME_FOLDER / f"{form_id}.json",
            self._root / f"{form_id}.json",
        )
        return next((path for path in candidates if path.exists()), None)

    def _remove_other_copies(self, form_id: str, *, keep: Path) -> None:
        for candidate in (
            self._root / self.DEPTH_FOLDER / f"{form_id}.json",
            self._root / self.TIME_FOLDER / f"{form_id}.json",
            self._root / f"{form_id}.json",
        ):
            if candidate != keep:
                candidate.unlink(missing_ok=True)
