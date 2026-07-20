from __future__ import annotations

import json
import os
from pathlib import Path
import tempfile

from geoworkbench.forms.codec import FormFormatError, form_from_dict, form_to_dict
from geoworkbench.forms.models import FormDocument


class FormRepository:
    def __init__(self, root: Path) -> None:
        self._root = root
        self._load_errors: list[tuple[Path, str]] = []

    @property
    def root(self) -> Path:
        return self._root

    @property
    def load_errors(self) -> tuple[tuple[Path, str], ...]:
        return tuple(self._load_errors)

    def save(self, form: FormDocument) -> Path:
        if form.read_only:
            raise PermissionError("Заводскую форму нельзя сохранять как пользовательскую")
        self._root.mkdir(parents=True, exist_ok=True)
        target = self._root / f"{form.form_id}.json"
        payload = json.dumps(form_to_dict(form), ensure_ascii=False, indent=2)
        fd, temp_name = tempfile.mkstemp(prefix=f".{target.name}.", suffix=".tmp", dir=self._root)
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as stream:
                stream.write(payload)
                stream.flush()
                os.fsync(stream.fileno())
            os.replace(temp_name, target)
        except Exception:
            Path(temp_name).unlink(missing_ok=True)
            raise
        return target

    def load(self, form_id: str) -> FormDocument:
        target = self._root / f"{form_id}.json"
        with target.open("r", encoding="utf-8") as stream:
            return form_from_dict(json.load(stream))

    def delete(self, form_id: str) -> None:
        (self._root / f"{form_id}.json").unlink(missing_ok=False)

    def list_forms(self) -> list[FormDocument]:
        self._load_errors = []
        if not self._root.exists():
            return []
        forms: list[FormDocument] = []
        for path in sorted(self._root.glob("*.json")):
            try:
                with path.open("r", encoding="utf-8") as stream:
                    forms.append(form_from_dict(json.load(stream)))
            except (OSError, json.JSONDecodeError, FormFormatError) as exc:
                # A single damaged legacy template must not make the whole form
                # manager unusable. Keep the file untouched and expose the
                # diagnostic so the UI/log can report it.
                self._load_errors.append((path, str(exc)))
        return forms
