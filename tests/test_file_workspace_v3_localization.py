from __future__ import annotations

from PySide6.QtWidgets import QApplication, QFrame, QLabel

from geoworkbench.ui.file_workspace_v3 import FileWorkspaceWidget


def _application() -> QApplication:
    application = QApplication.instance()
    if application is None:
        application = QApplication([])
    return application


def _label_texts(widget: FileWorkspaceWidget) -> list[str]:
    return [label.text() for label in widget.findChildren(QLabel)]


def test_help_cards_are_attached_to_the_correct_tabs() -> None:
    _application()
    widget = FileWorkspaceWidget(language="ru")
    expected = (
        "Как работать с документом",
        "Как работают PDF-инструменты",
        "Как создать логотип",
        "Как работать с архивами",
        "Как пользоваться расчётами",
    )
    for index, heading in enumerate(expected):
        page = widget.sections.widget(index)
        assert page is not None
        card = page.findChild(QFrame, "expertHelpCard")
        assert card is not None
        labels = card.findChildren(QLabel)
        assert labels and labels[0].text() == heading
    widget.deleteLater()


def test_kazakh_workspace_has_no_known_russian_visual_regressions() -> None:
    _application()
    widget = FileWorkspaceWidget(language="kk")
    texts = _label_texts(widget)
    forbidden = (
        "Пакетные операции с PDF",
        "Источники нового архива",
        "Результаты обновляются сразу",
        "Быстрый порядок работы",
        "Выделенная область",
        "Состояние",
    )
    assert not any(any(fragment in value for fragment in forbidden) for value in texts)
    assert any("PDF топтық операциялары" in value for value in texts)
    assert any("Жылдам жұмыс тәртібі" in value for value in texts)
    widget.deleteLater()


def test_english_workspace_has_no_known_russian_visual_regressions() -> None:
    _application()
    widget = FileWorkspaceWidget(language="en")
    texts = _label_texts(widget)
    forbidden = (
        "Пакетные операции с PDF",
        "Источники нового архива",
        "Результаты обновляются сразу",
        "Быстрый порядок работы",
        "Выделенная область",
        "Состояние",
    )
    assert not any(any(fragment in value for fragment in forbidden) for value in texts)
    assert any("Batch PDF operations" in value for value in texts)
    assert any("Quick workflow" in value for value in texts)
    widget.deleteLater()
