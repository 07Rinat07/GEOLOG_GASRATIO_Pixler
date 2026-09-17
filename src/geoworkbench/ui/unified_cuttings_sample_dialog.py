from __future__ import annotations

from typing import Any

from PySide6.QtWidgets import QFormLayout, QVBoxLayout, QWidget

from geoworkbench.domain.models import CuttingsSample
from geoworkbench.services.localization import AppLanguage
from geoworkbench.ui._unified_cuttings_sample_dialog_impl import (
    UnifiedCuttingsSampleDialog as _UnifiedCuttingsSampleDialogImpl,
)
from geoworkbench.ui.authored_source_language_selector import AuthoredSourceLanguageSelector


_INTERPRETATION_SOURCE_LABEL = {
    AppLanguage.RU: "Язык оригинала заключения",
    AppLanguage.KK: "Қорытындының түпнұсқа тілі",
    AppLanguage.EN: "Conclusion source language",
}


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
        self._interpretation_text_user_changed = False
        self._configure_interpretation_source_language()
        self.interpretation_input.textChanged.connect(
            self._mark_interpretation_text_changed
        )

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

    def _configure_interpretation_source_language(self) -> None:
        selector = AuthoredSourceLanguageSelector(
            self,
            language=self._language,
        )
        selector.setObjectName("cuttings-analysis-interpretation-source-language")
        if self._sample is not None:
            selector.load_existing(
                self._persisted_interpretation_source_language(self._sample)
            )
        self.interpretation_source_language_input = selector

        tab_index = self.tabs.indexOf(self.interpretation_input)
        if tab_index < 0:
            raise RuntimeError("Interpretation tab is not available")
        tab_label = self.tabs.tabText(tab_index)
        self.tabs.removeTab(tab_index)

        interpretation_widget = QWidget(self)
        interpretation_layout = QVBoxLayout(interpretation_widget)
        source_form = QFormLayout()
        source_form.addRow(
            _INTERPRETATION_SOURCE_LABEL[self._language],
            self.interpretation_source_language_input,
        )
        interpretation_layout.addLayout(source_form)
        interpretation_layout.addWidget(self.interpretation_input, 1)
        self.tabs.insertTab(tab_index, interpretation_widget, tab_label)

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

    def _persisted_interpretation_source_language(
        self, sample: CuttingsSample
    ) -> str | None:
        parent = self.parentWidget()
        controller = getattr(parent, "cuttings_controller", None)
        getter = getattr(controller, "analysis_interpretation_source_language", None)
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

    def _mark_interpretation_text_changed(self) -> None:
        self._interpretation_text_user_changed = True

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

        interpretation = self.interpretation_input.toPlainText().strip()
        interpretation_source = (
            self.interpretation_source_language_input.submitted_language()
        )
        localized_interpretation = (
            dict(self._sample.analysis_interpretation_i18n)
            if self._sample is not None
            else {}
        )

        ui_language = self._language.value
        if self._sample is None:
            if interpretation:
                localized_interpretation[ui_language] = interpretation
        elif self._interpretation_text_user_changed:
            if interpretation:
                localized_interpretation[ui_language] = interpretation
            else:
                localized_interpretation.pop(ui_language, None)

        # When the user explicitly changes provenance, the visible authored
        # conclusion is assigned to that source language. This makes the
        # controller's invariant explicit: a tracked source must contain text.
        if interpretation_source is not None:
            if interpretation:
                localized_interpretation[interpretation_source] = interpretation
            else:
                interpretation_source = None

        if localized_interpretation:
            values["analysis_interpretation_i18n"] = localized_interpretation
        values["analysis_interpretation_source_language"] = interpretation_source
        return values
