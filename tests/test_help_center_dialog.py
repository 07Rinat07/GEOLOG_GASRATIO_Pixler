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
        "project_title",
        "project_tokens",
        "tools_text",
        "print_text",
        "interpretation_text",
        "pdf_layout_text",
        "physical_print_text",
        "page_range_text",
        "details_text",
        "restore_text",
        "scale_text",
    ),
    (
        (
            AppLanguage.RU,
            "Документация и инструкции",
            "Проект и ежедневный LAS",
            (
                ".geologpkg",
                "первый LAS",
                "Ежедневно нарастить LAS",
                "дубликат",
                "конфликт",
                "Ctrl+S",
                "RU",
                "KK",
                "EN",
                "другой компьютер",
            ),
            "Файлы, PDF и калькуляторы",
            "Печать и отчёты",
            "перспективные интервалы",
            "Постраничный график газового каротажа",
            "Печать на физическом принтере Windows",
            "Диапазон 1–2",
            "форма реквизитов отчёта",
            "Подставить данные из программы",
            "промежуточные деления",
        ),
        (
            AppLanguage.KK,
            "Құжаттама және нұсқаулықтар",
            "Жоба және күнделікті LAS",
            (
                ".geologpkg",
                "Бірінші LAS",
                "LAS деректерін күнделікті өсіру",
                "қайталанатын",
                "қайшылық",
                "Ctrl+S",
                "RU",
                "KK",
                "EN",
                "Басқа компьютерге",
            ),
            "Файлдар, PDF және калькуляторлар",
            "Басып шығару және есептер",
            "перспективалы аралықтар",
            "Газ каротажының көпбетті графигі",
            "Windows жүйесіндегі физикалық принтерге басып шығару",
            "1–2 ауқымы",
            "есеп деректемелерінің пішіні",
            "Бағдарлама деректерін қою",
            "аралық бөліктер",
        ),
        (
            AppLanguage.EN,
            "Documentation and instructions",
            "Project and daily LAS",
            (
                ".geologpkg",
                "First LAS",
                "Append daily LAS data",
                "duplicate",
                "conflict",
                "Ctrl+S",
                "RU",
                "KK",
                "EN",
                "another computer",
            ),
            "Files, PDF, and calculators",
            "Printing and reports",
            "prospective intervals",
            "Multi-page mud-gas chart",
            "Printing to a physical Windows printer",
            "range of 1–2",
            "report-details form",
            "Restore application values",
            "intermediate ticks",
        ),
    ),
)
def test_help_content_is_complete_in_each_language(
    language: AppLanguage,
    title: str,
    project_title: str,
    project_tokens: tuple[str, ...],
    tools_text: str,
    print_text: str,
    interpretation_text: str,
    pdf_layout_text: str,
    physical_print_text: str,
    page_range_text: str,
    details_text: str,
    restore_text: str,
    scale_text: str,
) -> None:
    sections = help_sections(language)
    sections_by_key = {section.key: section for section in sections}
    pdf_help = pdf_layout_help_html(language)

    assert [section.key for section in sections] == [
        "overview",
        "project",
        "tools",
        "printing",
        "interpretation",
        "diagnostics",
    ]
    assert project_title == sections_by_key["project"].title
    project_html = " ".join(sections_by_key["project"].html.casefold().split())
    assert all(token.casefold() in project_html for token in project_tokens)
    assert tools_text == sections_by_key["tools"].title
    assert print_text == sections_by_key["printing"].title
    assert interpretation_text in interpretation_guide_html(language).casefold()
    assert pdf_layout_text in pdf_help
    assert physical_print_text in pdf_help
    assert page_range_text in pdf_help
    assert details_text in pdf_help
    assert restore_text in pdf_help
    assert scale_text in pdf_help
    assert all(section.html.strip() for section in sections)
    assert title


@pytest.mark.parametrize(
    ("language", "pdf_layout_text", "physical_print_text", "details_text"),
    (
        (
            AppLanguage.RU,
            "Постраничный график газового каротажа",
            "Печать на физическом принтере Windows",
            "форма реквизитов отчёта",
        ),
        (
            AppLanguage.KK,
            "Газ каротажының көпбетті графигі",
            "Windows жүйесіндегі физикалық принтерге басып шығару",
            "есеп деректемелерінің пішіні",
        ),
        (
            AppLanguage.EN,
            "Multi-page mud-gas chart",
            "Printing to a physical Windows printer",
            "report-details form",
        ),
    ),
)
def test_help_dialog_builds_all_sections(
    qapp,
    language: AppLanguage,
    pdf_layout_text: str,
    physical_print_text: str,
    details_text: str,
) -> None:
    dialog = HelpCenterDialog(language=language, section="interpretation")
    dialog.show()
    qapp.processEvents()

    assert dialog.sections.count() == 6
    assert dialog.current_section() == "interpretation"
    assert dialog.windowTitle()
    assert all(dialog.sections.tabText(index) for index in range(dialog.sections.count()))
    browser = dialog.sections.currentWidget()
    assert isinstance(browser, QTextBrowser)
    help_text = browser.toPlainText()
    assert pdf_layout_text in help_text
    assert physical_print_text in help_text
    assert details_text in help_text

    dialog.close()
