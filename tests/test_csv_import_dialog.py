from PySide6.QtWidgets import QDialogButtonBox, QTableWidget

from geoworkbench.services.localization import AppLanguage
from geoworkbench.ui.csv_import_dialog import CsvImportDialog


def test_csv_import_dialog_previews_and_returns_plan(qapp, tmp_path) -> None:
    source = tmp_path / "logging.csv"
    source.write_text("DEPT;C1\n100;1.2\n101;1.3\n", encoding="utf-8")

    dialog = CsvImportDialog(source)
    preview = dialog.findChild(QTableWidget, "csv-preview")

    assert preview is not None
    assert preview.rowCount() == 2
    assert preview.columnCount() == 2
    assert dialog.index_column.currentText() == "DEPT"
    plan = dialog.import_plan()
    assert plan.index_column == "DEPT"
    assert plan.encoding == "utf-8-sig"
    dialog.close()


def test_csv_import_dialog_allows_cp1251_reprobe(qapp, tmp_path) -> None:
    source = tmp_path / "russian.csv"
    source.write_bytes("ГЛУБИНА;ГАЗ\n100;1\n".encode("cp1251"))
    dialog = CsvImportDialog(source)

    assert dialog.index_column.count() == 0
    dialog.encoding.setCurrentText("cp1251")
    dialog._refresh_probe()

    assert dialog.index_column.currentText() == "ГЛУБИНА"
    dialog.close()


def test_csv_import_dialog_builds_composite_time_plan(qapp, tmp_path) -> None:
    source = tmp_path / "time.csv"
    source.write_text("DATE,TIME,C1\n15.07.2026,10:00:00,1\n", encoding="utf-8")
    dialog = CsvImportDialog(source)
    dialog.index_column.setCurrentText("DATE")
    dialog.composite_time.setChecked(True)
    dialog.time_column.setCurrentText("TIME")
    dialog.date_format.setText("%d.%m.%Y")
    dialog.time_format.setText("%H:%M:%S")
    dialog.timezone.setText("Asia/Oral")

    plan = dialog.import_plan()

    assert plan.index_column == "DATE"
    assert plan.time_column == "TIME"
    assert plan.date_format == "%d.%m.%Y"
    assert plan.timezone == "Asia/Oral"
    dialog.close()


def test_csv_import_dialog_uses_english_catalog(qapp, tmp_path) -> None:
    source = tmp_path / "logging.csv"
    source.write_text("DEPTH,C1\n100,1\n", encoding="utf-8")
    dialog = CsvImportDialog(source, language=AppLanguage.EN)
    buttons = dialog.findChild(QDialogButtonBox)

    assert dialog.windowTitle() == "CSV import — logging.csv"
    assert dialog.composite_time.text().startswith("Combine the DATE")
    assert dialog.timezone.placeholderText().startswith("for example")
    assert buttons.button(QDialogButtonBox.StandardButton.Cancel).text() == "Cancel"
    dialog.close()
