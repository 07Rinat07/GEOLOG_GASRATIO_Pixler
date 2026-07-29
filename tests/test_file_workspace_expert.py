from __future__ import annotations

from PySide6.QtWidgets import QApplication, QFrame, QLabel, QTabWidget, QToolButton

from geoworkbench.ui.file_workspace_expert import FileWorkspaceWidget


def _application() -> QApplication:
    application = QApplication.instance()
    if application is None:
        application = QApplication([])
    return application


def test_every_workspace_tab_has_visible_help() -> None:
    _application()
    widget = FileWorkspaceWidget(language="ru")

    cards = widget.findChildren(QFrame, "expertHelpCard")
    assert len(cards) == 5
    assert all(card.findChildren(QLabel) for card in cards)
    assert widget.findChild(QTabWidget, "petroleumCalculatorTabs") is not None

    widget.deleteLater()


def test_pdf_eraser_and_replacement_action_is_discoverable() -> None:
    _application()
    widget = FileWorkspaceWidget(language="ru")

    buttons = widget.findChildren(QToolButton)
    erasers = [button for button in buttons if button.text() == "Ластик / заменить"]
    assert len(erasers) == 1
    assert "удал" in erasers[0].toolTip().casefold()

    widget.deleteLater()


def test_datum_fields_have_full_names_and_units() -> None:
    _application()
    widget = FileWorkspaceWidget(language="ru")

    labels = [label.text() for label in widget.findChildren(QLabel)]
    assert any("пола буровой DF" in text for text in labels)
    assert any("роторного стола RT" in text for text in labels)
    assert all(control.suffix() == " м" for control in widget.datum_inputs)

    widget.deleteLater()
