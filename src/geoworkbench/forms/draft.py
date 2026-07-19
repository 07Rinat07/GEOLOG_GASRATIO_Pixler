from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass

from geoworkbench.forms.models import FormDocument


@dataclass(slots=True)
class DraftFormController:
    """Own the saved and mutable draft snapshots of one user form."""

    _saved: FormDocument
    _draft: FormDocument
    revision: int = 0

    @classmethod
    def create(cls, form: FormDocument) -> "DraftFormController":
        saved = deepcopy(form)
        return cls(saved, deepcopy(saved))

    @property
    def form(self) -> FormDocument:
        return self._draft

    @property
    def dirty(self) -> bool:
        return self._draft != self._saved

    def changed(self) -> None:
        self.revision += 1

    def revert(self) -> FormDocument:
        self._draft = deepcopy(self._saved)
        self.revision += 1
        return self._draft

    def mark_saved(self) -> FormDocument:
        self._draft.validate()
        self._saved = deepcopy(self._draft)
        self.revision += 1
        return self._saved

    def saved_copy(self) -> FormDocument:
        return deepcopy(self._saved)
