from openpyxl import load_workbook
import pytest

from geoworkbench.printing.interpretation_report import build_interpretation_report, _LABELS
from geoworkbench.printing.interpretation_report_office import export_interpretation_report_xlsx
from geoworkbench.services.localization import AppLanguage
from test_interpretation_report import _session


@pytest.mark.parametrize("language, expected", [
    (AppLanguage.RU, "Единица измерения"),
    (AppLanguage.KK, "Өлшем бірлігі"),
    (AppLanguage.EN, "Unit"),
])
def test_geology_xlsx_unit_header_uses_output_language(tmp_path, language, expected):
    session = _session()
    report = build_interpretation_report(session, language=language)
    before = repr(report)
    path = tmp_path / "geology.xlsx"
    export_interpretation_report_xlsx(report, path, language=language)
    book = load_workbook(path)
    try:
        sheet = book[_LABELS[language]["gas_lba_section"][:31]]
        assert sheet["C1"].value == expected
        assert sheet["C1"].alignment.wrap_text
        assert tuple(cell.value for cell in sheet[1]) == (
            _LABELS[language]["interval"], _LABELS[language]["name"], expected,
            _LABELS[language]["minimum"], _LABELS[language]["mean"], _LABELS[language]["maximum"],
        )
    finally:
        book.close()
    assert repr(report) == before
