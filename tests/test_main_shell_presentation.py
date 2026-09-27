from __future__ import annotations

import re
from pathlib import Path


def test_main_window_exposes_stable_shell_presentation_hooks() -> None:
    source = Path("src/geoworkbench/ui/main_window.py").read_text(encoding="utf-8")

    assert 'self.setObjectName("mainWindow")' in source
    assert 'self.tabs.setObjectName("workspaceTabs")' in source
    assert "self.tabs.setDocumentMode(True)" in source
    assert 'status_bar.setObjectName("mainStatusBar")' in source
    assert "self.left_panel_rail.setStyleSheet" not in source
    assert "self.right_panel_rail.setStyleSheet" not in source
    assert "self.left_panel_rail.setMinimumWidth(40)" in source
    assert "self.right_panel_rail.setMinimumWidth(40)" in source


def test_home_dashboard_is_palette_aware_and_adaptive() -> None:
    source = Path("src/geoworkbench/ui/home_page.py").read_text(encoding="utf-8")

    assert "palette(window)" in source
    assert "palette(highlight)" in source
    assert "palette(button-text)" in source
    assert "dark_surface = self.palette().color(" in source
    assert "columns = 3 if viewport_width >= 1080" in source
    assert "QScrollBar::handle:vertical:hover" in source
    assert re.search(r"#[0-9a-fA-F]{3,8}\\b", source) is None


def test_application_main_shell_style_has_no_fixed_theme_colours() -> None:
    source = Path("src/geoworkbench/ui/application_style.py").read_text(encoding="utf-8")

    main_shell = source.split("QMainWindow#mainWindow", 1)[1].split(
        "QFrame#formEditToolbar", 1
    )[0]
    assert "QToolBar#leftPanelRail" in main_shell
    assert "QTabWidget#workspaceTabs" in main_shell
    assert "QStatusBar#mainStatusBar" in main_shell
    assert "QDockWidget::title" in main_shell
    assert re.search(r"#[0-9a-fA-F]{3,8}\\b", main_shell) is None



def test_product_branding_uses_exact_gasratio_pixler_name() -> None:
    exact_name = "DIGITAL GEOLOG GASRATIO&PIXLER"
    brand = Path("src/geoworkbench/brand.py").read_text(encoding="utf-8")
    home_page = Path("src/geoworkbench/ui/home_page.py").read_text(encoding="utf-8")
    main_window = Path("src/geoworkbench/ui/main_window.py").read_text(encoding="utf-8")
    report_visual = Path("src/geoworkbench/printing/report_visual_system.py").read_text(
        encoding="utf-8"
    )

    assert f'APPLICATION_DISPLAY_NAME = "{exact_name}"' in brand
    assert "self.title.setText(APPLICATION_DISPLAY_NAME)" in home_page
    assert "APPLICATION_DISPLAY_NAME" in main_window
    assert "GASRATIO@Pixler" not in main_window
    assert "from geoworkbench.brand import REPORT_BRAND_WORDMARK" in report_visual
