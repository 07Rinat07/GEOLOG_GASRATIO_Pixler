from PySide6.QtWidgets import QTableWidget

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
