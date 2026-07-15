from __future__ import annotations

import sys

from PySide6.QtWidgets import QApplication

from geoworkbench.ui.main_window import MainWindow
from geoworkbench.ui.branding import application_icon


def main() -> int:
    app = QApplication(sys.argv)
    app.setApplicationName("GEOLOG GASRATIO@Pixler")
    app.setOrganizationName("GeoLog")
    app.setWindowIcon(application_icon())
    window = MainWindow()
    window.show()
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
