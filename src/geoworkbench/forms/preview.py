from __future__ import annotations

from dataclasses import dataclass
from typing import Callable

from geoworkbench.forms.models import FormDocument

PreviewCallback = Callable[[FormDocument], None]


@dataclass(slots=True)
class FormPreviewController:
    callback: PreviewCallback | None = None
    auto_apply: bool = True
    pending: bool = False
    apply_count: int = 0

    def changed(self, form: FormDocument) -> None:
        self.pending = True
        if self.auto_apply:
            self.apply(form)

    def apply(self, form: FormDocument) -> None:
        if self.callback is not None:
            self.callback(form)
        self.pending = False
        self.apply_count += 1
