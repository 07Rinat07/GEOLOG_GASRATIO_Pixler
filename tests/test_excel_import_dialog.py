from openpyxl import Workbook

from geoworkbench.ui.excel_import_dialog import ExcelImportDialog


def test_excel_dialog_selects_sheet_header_and_index(qapp, tmp_path) -> None:
    source = tmp_path / "logging.xlsx"
    workbook = Workbook()
    sheet = workbook.active
    sheet.title = "Logging"
    sheet.append(["title", None])
    sheet.append(["DEPTH", "C1"])
    sheet.append([100.0, 1.0])
    workbook.save(source)

    dialog = ExcelImportDialog(source)
    dialog.header_row.setValue(2)
    dialog.index_column.setCurrentText("DEPTH")

    plan = dialog.import_plan()

    assert plan.sheet_name == "Logging"
    assert plan.header_row == 2
    assert plan.index_column == "DEPTH"
    dialog.close()
