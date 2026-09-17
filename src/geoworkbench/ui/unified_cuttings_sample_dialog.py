from __future__ import annotations

from typing import Any

from PySide6.QtWidgets import QFormLayout, QLineEdit, QPlainTextEdit, QVBoxLayout, QWidget

from geoworkbench.domain.models import CuttingsSample
from geoworkbench.services.localization import AppLanguage
from geoworkbench.ui._unified_cuttings_sample_dialog_impl import (
    UnifiedCuttingsSampleDialog as _UnifiedCuttingsSampleDialogImpl,
)
from geoworkbench.ui.authored_source_language_selector import AuthoredSourceLanguageSelector


_SOURCE_LABELS = {
    AppLanguage.RU: {
        "lba": "Язык оригинала описания ЛБА",
        "interpretation": "Язык оригинала заключения",
    },
    AppLanguage.KK: {
        "lba": "ЛБА сипаттамасының түпнұсқа тілі",
        "interpretation": "Қорытындының түпнұсқа тілі",
    },
    AppLanguage.EN: {
        "lba": "LBA description source language",
        "interpretation": "Conclusion source language",
    },
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

    def _analysis_widget(self, sample: CuttingsSample | None) -> QWidget:
        widget = super()._analysis_widget(sample)
        self.lba_description_source_language_input = AuthoredSourceLanguageSelector(
            widget,
            language=self._language,
        )
        self.lba_description_source_language_input.setObjectName(
            "lba-description-source-language"
        )
        if sample is not None:
            self.lba_description_source_language_input.load_existing(
                self._persisted_analysis_source_language(
                    sample,
                    "lba_description_source_language",
                )
            )
        layout = widget.layout()
        if not isinstance(layout, QVBoxLayout):
            raise RuntimeError("Unexpected unified analysis layout")
        form = QFormLayout()
        form.addRow(
            _SOURCE_LABELS[self._language]["lba"],
            self.lba_description_source_language_input,
        )
        layout.insertLayout(max(0, layout.count() - 1), form)
        return widget

    def _interpretation_widget(self, sample: CuttingsSample | None) -> QWidget:
        widget = super()._interpretation_widget(sample)
        self.interpretation_source_language_input = AuthoredSourceLanguageSelector(
            widget,
            language=self._language,
        )
        self.interpretation_source_language_input.setObjectName(
            "analysis-interpretation-source-language"
        )
        if sample is not None:
            self.interpretation_source_language_input.load_existing(
                self._persisted_analysis_source_language(
                    sample,
                    "analysis_interpretation_source_language",
                )
            )
        layout = widget.layout()
        if not isinstance(layout, QVBoxLayout):
            raise RuntimeError("Unexpected unified interpretation layout")
        form = QFormLayout()
        form.addRow(
            _SOURCE_LABELS[self._language]["interpretation"],
            self.interpretation_source_language_input,
        )
        layout.insertLayout(0, form)
        return widget

    def _persisted_analysis_source_language(
        self,
        sample: CuttingsSample,
        getter_name: str,
    ) -> str | None:
        parent = self.parentWidget()
        controller = getattr(parent, "cuttings_controller", None)
        getter = getattr(controller, getter_name, None)
        if not callable(getter):
            return None
        try:
            value = getter(sample.sample_id)
        except (KeyError, RuntimeError, ValueError):
            return None
        if value is None:
            return None
        try:
            return AppLanguage(str(value)).value
        except ValueError:
            return None

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
        values["lba_description_source_language"] = self._analysis_source_payload(
            self.lba_description_source_language_input,
            self.lba_description_inputs,
            values,
            localized_key="lba_description_i18n",
        )
        values["analysis_interpretation_source_language"] = self._analysis_source_payload(
            self.interpretation_source_language_input,
            self.interpretation_inputs,
            values,
            localized_key="analysis_interpretation_i18n",
        )
        return values

    def _analysis_source_payload(
        self,
        selector: AuthoredSourceLanguageSelector,
        editors: dict[str, QLineEdit | QPlainTextEdit],
        values: dict[str, Any],
        *,
        localized_key: str,
    ) -> str | None:
        source_language = selector.submitted_language()
        if source_language is None:
            return None

        editor = editors[source_language]
        text = (
            editor.text()
            if isinstance(editor, QLineEdit)
            else editor.toPlainText()
        ).strip()

        # New composition-only samples must not acquire authored provenance
        # before the corresponding source-language editor actually contains text.
        if self._sample is None and not text:
            return None

        localized = values.get(localized_key)
        if not isinstance(localized, dict):
            raise TypeError(f"{localized_key} must be a mapping")
        if text:
            localized[source_language] = text
        return source_language
