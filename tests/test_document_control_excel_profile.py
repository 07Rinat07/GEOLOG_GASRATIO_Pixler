from dataclasses import replace

from openpyxl import Workbook, load_workbook
import pytest

from geoworkbench.data import report_document_control_excel as excel
from geoworkbench.printing.report_document_control import ReportDocumentControl
from geoworkbench.printing.report_visual_system import modern_oilfield_report_profile
from geoworkbench.services.localization import AppLanguage


@pytest.mark.parametrize("language", list(AppLanguage))
@pytest.mark.parametrize("grayscale", [False, True])
def test_document_control_profile_survives_xlsx_reopen(tmp_path, monkeypatch, language, grayscale):
    visual = modern_oilfield_report_profile(grayscale=grayscale)
    visual = replace(visual, typography=replace(
        visual.typography, title_pt=24, subtitle_pt=11, section_pt=14, body_pt=9, footer_pt=6,
    ))
    monkeypatch.setattr(excel, "modern_oilfield_report_profile", lambda: visual)
    snapshot = ReportDocumentControl(
        title="Отчёт / Есеп / Report Әғқң", subtitle="Подзаголовок / Subtitle",
        control=(("ID", "=2+2"),), context=(("Скважина", "Well 42"),),
        approvals=(), notes=("@literal note",),
    )
    workbook = Workbook()
    workbook.active.append(("source", 42))
    excel.write_document_control_sheet(workbook, snapshot, language)
    path = tmp_path / "control.xlsx"
    workbook.save(path)
    workbook.close()
    restored = load_workbook(path)
    try:
        sheet = restored.worksheets[-1]
        assert restored.worksheets[0]["B1"].value == 42
        assert sheet["A2"].value == snapshot.title
        assert sheet["A3"].value == snapshot.subtitle
        for address, size, color in (
            ("A1", 14, visual.palette.accent),
            ("A2", 24, visual.palette.text),
            ("A3", 11, visual.palette.text_secondary),
            ("B4", 9, visual.palette.text),
        ):
            assert sheet[address].font.sz == size
            assert sheet[address].font.color.rgb[-6:] == color[1:]
            assert sheet[address].alignment.wrap_text
        assert sheet["A1"].font.bold and sheet["A2"].font.bold
        assert not any(cell.data_type == "f" for row in sheet for cell in row)
        assert sheet["B5"].value.lstrip("'") == "=2+2"
        assert sheet["A6"].value.lstrip("'") == "@literal note"
        assert {str(item) for item in sheet.merged_cells.ranges} == {"A1:B1", "A2:B2", "A3:B3"}
        assert sheet.print_title_rows == "$1:$3"
        assert sheet.page_setup.fitToWidth == 1
        assert sheet.page_setup.fitToHeight == 0
        for part in (sheet.oddFooter.left, sheet.oddFooter.right):
            assert part.size == 6
            assert part.color == visual.palette.text_muted[1:].upper()
        assert sheet.oddFooter.left.text == visual.brand_wordmark.replace("&", "&&")
        assert sheet.oddFooter.right.text == "&P / &N"
    finally:
        restored.close()
