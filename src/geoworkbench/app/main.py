from __future__ import annotations

import sys

from PySide6.QtWidgets import QApplication, QInputDialog

from geoworkbench.services.localization import (
    LANGUAGE_NAMES,
    AppLanguage,
    LanguageSettings,
    Localizer,
)
from geoworkbench.printing.unicode_support import configure_application_unicode_fonts
from geoworkbench.ui.main_window import MainWindow
from geoworkbench.ui.branding import application_icon


def main() -> int:
    app = QApplication(sys.argv)
    app.setApplicationName("GEOLOG GASRATIO@Pixler")
    app.setOrganizationName("GeoLog")
    app.setWindowIcon(application_icon())
    configure_application_unicode_fonts(app)
    settings = LanguageSettings.system()
    language = settings.current()
    if language is None:
        localizer = Localizer.create(AppLanguage.RU)
        names = [LANGUAGE_NAMES[item] for item in AppLanguage]
        selected, accepted = QInputDialog.getItem(
            None,
            localizer.text("language.first.title"),
            localizer.text("language.first.prompt"),
            names,
            0,
            False,
        )
        language = next(
            (item for item, name in LANGUAGE_NAMES.items() if name == selected),
            AppLanguage.RU,
        )
        if accepted:
            settings.save(language)
    window = MainWindow(language=language, language_settings=settings)
    window.show()
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
