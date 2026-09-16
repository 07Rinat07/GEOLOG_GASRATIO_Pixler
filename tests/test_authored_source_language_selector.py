from __future__ import annotations

import pytest
from PySide6.QtWidgets import QApplication

from geoworkbench.services.localization import AppLanguage
from geoworkbench.ui.authored_source_language_selector import AuthoredSourceLanguageSelector


def _app() -> QApplication:
    return QApplication.instance() or QApplication([])


def test_new_content_defaults_to_current_ui_language_and_submits_it() -> None:
    _app()
    selector = AuthoredSourceLanguageSelector(language=AppLanguage.KK)

    assert selector.current_language_code() == "kk"
    assert selector.submitted_language() == "kk"


def test_existing_content_displays_persisted_language_without_resubmitting_it() -> None:
    _app()
    selector = AuthoredSourceLanguageSelector(
        language=AppLanguage.EN,
        persisted_language="kk",
        preserve_existing=True,
    )

    assert selector.current_language_code() == "kk"
    assert selector.submitted_language() is None


def test_existing_content_submits_language_only_after_explicit_change() -> None:
    _app()
    selector = AuthoredSourceLanguageSelector(
        language=AppLanguage.RU,
        persisted_language="kk",
        preserve_existing=True,
    )

    selector.set_language_code("en")

    assert selector.current_language_code() == "en"
    assert selector.submitted_language() == "en"


def test_existing_content_rejects_unknown_persisted_language_fail_closed() -> None:
    _app()

    with pytest.raises(ValueError, match="Unsupported persisted authored source language"):
        AuthoredSourceLanguageSelector(
            language=AppLanguage.RU,
            persisted_language="de",
            preserve_existing=True,
        )


def test_programmatic_selection_rejects_unknown_language() -> None:
    _app()
    selector = AuthoredSourceLanguageSelector(language=AppLanguage.RU)

    with pytest.raises(ValueError, match="Unsupported authored source language"):
        selector.set_language_code("de")
