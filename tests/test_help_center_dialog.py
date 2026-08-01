from __future__ import annotations

import pytest
from PySide6.QtWidgets import QTextBrowser

from geoworkbench.services.localization import AppLanguage
from geoworkbench.ui.help_center_dialog import HelpCenterDialog
from geoworkbench.ui.help_content import help_sections, interpretation_guide_html
from geoworkbench.ui.help_pdf_layout_content import pdf_layout_help_html


@pytest.mark.parametrize(
    (
        "language",
        "title",
        "tools_text",
        "print_text",
        "interpretation_text",
        "pdf_layout_text",
    ),
    (
        (
            AppLanguage.RU,
            "Документация и инструкции",
            "Файлы, PDF и калькуляторы",
            "Печать и отчёты",
            "перспективные интервалы",
            "Постраничный график газового каротажа",
        ),
        (
            AppLanguage.KK,
            "Құжаттама және нұсқаулықтар",
            "Файлдар, PDF және калькуляторлар",
            "Басып шығару және есептер",
            "перспективалы аралықтар",
            "Газ каротажының көпбетті графигі",
        ),
        (
            AppLanguage.EN,
            "Documentation and instructions",
            "Files, PDF, and calculators",
            "Printing and reports",
            "prospective intervals",
            "Multi-page mud-gas chart",
        ),
    ),
)
def test_help_content_is_complete_in_each_language(
    language: AppLanguage,
    title: str,
    tools_text: str,
    print_text: str,
    interpretation_text: str,
    pdf_layout_text: str,
) -> None:
    sections = help_sections(language)

    assert [section.key for section in sections] == [
        "overview",
        "tools",
        "printing",
        "interpretation",
        "diagnostics",
    ]
    assert tools_text == sections[1].title
    assert print_text == sections[2].title
    assert interpretation_text in interpretation_guide_html(language).casefold()
    assert pdf_layout_text in pdf_layout_help_html(language)
    assert all(section.html.strip() for section in sections)
    assert title


@pytest.mark.parametrize(
    ("language", "pdf_layout_text"),
    (
        (AppLanguage.RU, "Постраничный график газового каротажа"),
        (AppLanguage.KK, "Газ каротажының көпбетті графигі"),
        (AppLanguage.EN, "Multi-page mud-gas chart"),
    ),
)
def test_help_dialog_builds_all_sections(
    qapp,
    language: AppLanguage,
    pdf_layout_text: str,
) -> None:
    dialog = HelpCenterDialog(language=language, section="interpretation")
    dialog.show()
    qapp.processEvents()

    assert dialog.sections.count() == 5
    assert dialog.current_section() == "interpretation"
    assert dialog.windowTitle()
    assert all(dialog.sections.tabText(index) for index in range(dialog.sections.count()))
    browser = dialog.sections.currentWidget()
    assert isinstance(browser, QTextBrowser)
    assert pdf_layout_text in browser.toPlainText()

    dialog.close()
