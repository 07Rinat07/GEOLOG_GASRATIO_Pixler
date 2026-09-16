from __future__ import annotations

from PySide6.QtWidgets import QComboBox, QWidget

from geoworkbench.services.localization import AppLanguage, LANGUAGE_NAMES


_UNSET_LABELS = {
    AppLanguage.RU: "Язык оригинала не задан",
    AppLanguage.KK: "Түпнұсқа тілі көрсетілмеген",
    AppLanguage.EN: "Source language is not set",
}


class AuthoredSourceLanguageSelector(QComboBox):
    """Reusable selector for an authored field's original language provenance.

    New authored content submits the current UI language by default. Existing
    content can be loaded repeatedly into the same selector while preserving
    either its recorded provenance or the absence of provenance until the user
    explicitly selects another language.
    """

    def __init__(
        self,
        parent: QWidget | None = None,
        *,
        language: AppLanguage = AppLanguage.RU,
        persisted_language: str | None = None,
        preserve_existing: bool = False,
    ) -> None:
        super().__init__(parent)
        self.setObjectName("authored-source-language-selector")
        self._ui_language = language
        self._preserve_existing = False
        self._initial_language: str | None = None

        if preserve_existing:
            self.load_existing(persisted_language)
            return

        selected = self._normalize_initial_language(
            language,
            persisted_language=persisted_language,
            preserve_existing=False,
        )
        self._initial_language = selected
        self._populate(selected)

    @staticmethod
    def _normalize_initial_language(
        language: AppLanguage,
        *,
        persisted_language: str | None,
        preserve_existing: bool,
    ) -> str:
        if persisted_language is None:
            return language.value
        try:
            return AppLanguage(persisted_language).value
        except ValueError as exc:
            if preserve_existing:
                raise ValueError(
                    f"Unsupported persisted authored source language: {persisted_language!r}"
                ) from exc
            return language.value

    @staticmethod
    def _normalize_persisted_language(language: str) -> str:
        try:
            return AppLanguage(language).value
        except ValueError as exc:
            raise ValueError(
                f"Unsupported persisted authored source language: {language!r}"
            ) from exc

    def _populate(self, selected: str | None, *, include_unset: bool = False) -> None:
        self.clear()
        if include_unset:
            self.addItem(_UNSET_LABELS[self._ui_language], None)
        for content_language in AppLanguage:
            self.addItem(LANGUAGE_NAMES[content_language], content_language.value)

        index = self.findData(selected)
        if index < 0:
            raise ValueError(f"Unsupported authored source language: {selected!r}")
        self.setCurrentIndex(index)

    def load_existing(self, persisted_language: str | None) -> None:
        """Load one existing field without implicitly changing provenance.

        A tracked field displays its recorded source language. A legacy field
        with no provenance displays an explicit unset state. In both cases the
        submitted payload remains ``None`` until the user makes a language
        choice that differs from the loaded provenance.
        """

        self._preserve_existing = True
        if persisted_language is None:
            self._initial_language = None
            self._populate(None, include_unset=True)
            return

        normalized = self._normalize_persisted_language(persisted_language)
        self._initial_language = normalized
        self._populate(normalized)

    def reset_for_new(self) -> None:
        """Reset the selector for a newly authored field."""

        self._preserve_existing = False
        self._initial_language = self._ui_language.value
        self._populate(self._initial_language)

    def selected_language_code(self) -> str | None:
        """Return the visible language code, or ``None`` for legacy unset state."""

        value = self.currentData()
        if value is None:
            return None
        if not isinstance(value, str) or not value:
            raise RuntimeError("Authored source language selector has invalid item data")
        return value

    def current_language_code(self) -> str:
        value = self.selected_language_code()
        if value is None:
            raise RuntimeError("Authored source language selector has no source language")
        return value

    def submitted_language(self) -> str | None:
        """Return the controller payload for the current selection.

        Existing content returns ``None`` while its loaded provenance remains
        unchanged. Legacy content also returns ``None`` while the explicit
        unset state remains selected.
        """

        current = self.selected_language_code()
        if current is None:
            return None
        if self._preserve_existing and current == self._initial_language:
            return None
        return current

    def set_language_code(self, language: str) -> None:
        try:
            normalized = AppLanguage(language).value
        except ValueError as exc:
            raise ValueError(f"Unsupported authored source language: {language!r}") from exc
        index = self.findData(normalized)
        if index < 0:
            raise ValueError(f"Unsupported authored source language: {language!r}")
        self.setCurrentIndex(index)
