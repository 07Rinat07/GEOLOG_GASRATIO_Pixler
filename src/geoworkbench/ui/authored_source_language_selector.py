from __future__ import annotations

from PySide6.QtWidgets import QComboBox, QWidget

from geoworkbench.services.localization import AppLanguage, LANGUAGE_NAMES


class AuthoredSourceLanguageSelector(QComboBox):
    """Reusable selector for an authored field's original language provenance.

    New authored content submits the current UI language by default.  Existing
    tracked content can display its persisted source language while returning
    ``None`` until the user explicitly changes the selection, allowing
    controllers to preserve the recorded provenance without a redundant write.
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
        self._preserve_existing = preserve_existing
        self._initial_language = self._normalize_initial_language(
            language,
            persisted_language=persisted_language,
            preserve_existing=preserve_existing,
        )
        self._populate(self._initial_language)

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

    def _populate(self, selected: str) -> None:
        self.clear()
        for content_language in AppLanguage:
            self.addItem(LANGUAGE_NAMES[content_language], content_language.value)
        index = self.findData(selected)
        if index < 0:
            raise ValueError(f"Unsupported authored source language: {selected!r}")
        self.setCurrentIndex(index)

    def current_language_code(self) -> str:
        value = self.currentData()
        if not isinstance(value, str) or not value:
            raise RuntimeError("Authored source language selector has no valid language")
        return value

    def submitted_language(self) -> str | None:
        """Return the controller payload for the current selection.

        Existing tracked content returns ``None`` while the selection remains
        unchanged so the application layer preserves persisted provenance.
        """

        current = self.current_language_code()
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
