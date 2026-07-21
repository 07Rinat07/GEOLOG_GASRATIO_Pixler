from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtGui import QColor, QPalette

from geoworkbench.forms.models import FormAxisKind, FormDocument
from geoworkbench.forms.repository import FormRepository
from geoworkbench.ui.form_manager_dialog import FormManagerDialog


def test_form_library_text_remains_visible_with_dark_application_palette(qapp, tmp_path) -> None:
    original = qapp.palette()
    dark = QPalette(original)
    dark.setColor(QPalette.ColorRole.Window, QColor("#202124"))
    dark.setColor(QPalette.ColorRole.WindowText, Qt.GlobalColor.white)
    dark.setColor(QPalette.ColorRole.Base, QColor("#202124"))
    dark.setColor(QPalette.ColorRole.Text, Qt.GlobalColor.white)
    dark.setColor(QPalette.ColorRole.Button, QColor("#303134"))
    dark.setColor(QPalette.ColorRole.ButtonText, Qt.GlobalColor.white)
    qapp.setPalette(dark)
    try:
        repository = FormRepository(tmp_path / "forms")
        repository.save(FormDocument.create("Моя глубинная форма", FormAxisKind.DEPTH))
        repository.save(FormDocument.create("Моя временная форма", FormAxisKind.TIME))

        dialog = FormManagerDialog(repository, language="ru")
        dialog.show()
        qapp.processEvents()

        groups = [
            dialog.tree_widget.topLevelItem(index)
            for index in range(dialog.tree_widget.topLevelItemCount())
        ]
        assert [group.text(0) for group in groups] == [
            "Заводские формы — глубина  (2)",
            "Заводские формы — время  (1)",
            "Пользовательские формы — глубина  (1)",
            "Пользовательские формы — время  (1)",
        ]
        assert all(group.foreground(0).color() == QColor(Qt.GlobalColor.black) for group in groups)

        factory_names = [groups[0].child(index).text(0) for index in range(groups[0].childCount())]
        assert any("Глубинка — геология, технология и газ" in name for name in factory_names)
        assert any("МАСТЕРЛОГ" in name for name in factory_names)
        assert groups[2].child(0).text(0) == "Моя глубинная форма"
        assert groups[3].child(0).text(0) == "Моя временная форма"
        assert groups[0].child(0).foreground(0).color() == QColor(Qt.GlobalColor.black)
    finally:
        qapp.setPalette(original)
