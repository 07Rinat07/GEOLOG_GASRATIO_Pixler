from __future__ import annotations

from typing import Any

from PySide6.QtWidgets import QWidget

from geoworkbench.domain.models import CuttingsSample
from geoworkbench.services.localization import AppLanguage
from geoworkbench.ui._unified_cuttings_sample_dialog_impl import (
    UnifiedCuttingsSampleDialog as _UnifiedCuttingsSampleDialogImpl,
)


class UnifiedCuttingsSampleDialog(_UnifiedCuttingsSampleDialogImpl):
    """Public cuttings dialog with source-language provenance coordination.

    The implementation widget stays focused on editing sample content. This
    adapter coordinates persisted provenance through the public controller
    contract exposed by the parent MainWindow and keeps unchanged edits
    semantically distinct from an explicit source-language change.
    """

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        self._description_source_language_user_changed = False
        super().__init__(*args, **kwargs)

    def _description_widget(self, sample: CuttingsSample | None) -> QWidget:
        widget = super()._description_widget(sample)
        persisted_source = self._persisted_description_source_language(sample)
        if persisted_source is not None:
            index = self.description_source_language_input.findData(persisted_source)
            if index >= 0:
                self.description_source_language_input.setCurrentIndex(index)
        self.description_source_language_input.currentIndexChanged.connect(
            self._mark_description_source_language_changed
        )
        return widget

    def _persisted_description_source_language(
        self, sample: CuttingsSample | None
    ) -> str | None:
        if sample is None:
            return None
        parent = self.parentWidget()
        controller = getattr(parent, "cuttings_controller", None)
        getter = getattr(controller, "description_source_language", None)
        if not callable(getter):
            return None
        try:
            value = getter(sample.sample_id)
        except (KeyError, RuntimeError):
            return None
        if value is None:
            return None
        try:
            return AppLanguage(str(value)).value
        except ValueError:
            return None

    def _mark_description_source_language_changed(self, _index: int = -1) -> None:
        self._description_source_language_user_changed = True

    def values(self) -> dict[str, Any]:
        values = super().values()
        raw_source = self.description_source_language_input.currentData()
        source_language = str(raw_source) if raw_source is not None else None

        # Merely opening an existing tracked sample must not be interpreted as
        # an authored provenance change. The controller will preserve the
        # persisted source when this value is None.
        if self._sample is not None and not self._description_source_language_user_changed:
            source_language = None
        elif source_language is not None:
            source_editor = self.description_editors[source_language]
            source_html = source_editor.html()
            descriptions = values["description_i18n"]
            if not isinstance(descriptions, dict):
                raise TypeError("description_i18n must be a mapping")

            # Legacy samples may show sample.description in the RU editor even
            # though description_i18n has no RU entry. Selecting RU explicitly
            # promotes the visible authored text into the localized payload.
            if source_html is not None:
                descriptions[source_language] = source_html

            # A new composition/analysis-only sample is valid without a text
            # provenance record. Keep the visual language default, but do not
            # start tracking until that source editor actually contains text.
            if self._sample is None and source_html is None:
                source_language = None

        values["description_source_language"] = source_language
        return values
