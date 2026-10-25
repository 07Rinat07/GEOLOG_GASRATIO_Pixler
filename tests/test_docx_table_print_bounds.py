"""Word tables must never extend beyond the A4 landscape printable body."""

from xml.etree import ElementTree as ET

import pytest

from geoworkbench.data.hydrocarbon_interpretation_export import (
    _MAX_BODY_TABLE_WIDTH_TWIPS,
    _fit_table_widths,
    _table,
)


W = "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}"


@pytest.mark.parametrize("widths", (
    (2400, 1000, 2200, 4700, 4800),  # Methodology
    (2100, 1600, 3000, 5000, 3400),  # Candidate intervals
    (1700, 1700, 1200, 1800, 2100, 3600, 1700, 1700, 2000),  # Gas context
    (1000, 2000),  # Deliberately small legal table
))
def test_docx_table_grid_and_cells_fit_a4_landscape(widths: tuple[int, ...]) -> None:
    names = tuple(f"Column {n}" for n in range(len(widths)))
    fragment = _table(names, (names,), widths=widths)
    root = ET.fromstring(
        '<root xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">'
        + fragment + "</root>"
    )
    table = root.find(W + "tbl")
    assert table is not None
    props = table.find(W + "tblPr")
    assert props is not None
    table_width = props.find(W + "tblW")
    assert table_width is not None
    declared = int(table_width.attrib[W + "w"])
    assert declared <= _MAX_BODY_TABLE_WIDTH_TWIPS
    assert declared < 16838 - 2 * 850  # A4 page and configured body margins.
    grid = table.find(W + "tblGrid")
    assert grid is not None
    grid_widths = [int(cell.attrib[W + "w"]) for cell in grid]
    assert len(grid_widths) == len(widths)
    assert sum(grid_widths) == declared
    for row in table.findall(W + "tr"):
        assert [
            int(cell.find(W + "tcPr").find(W + "tcW").attrib[W + "w"])
            for cell in row.findall(W + "tc")
        ] == grid_widths
    assert props.find(W + "jc").attrib[W + "val"] == "center"


def test_table_width_weights_preserved_and_invalid_inputs_fail_closed() -> None:
    scaled = _fit_table_widths((2400, 1000, 2200, 4700, 4800))
    assert sum(scaled) == _MAX_BODY_TABLE_WIDTH_TWIPS
    assert all(value > 0 for value in scaled)
    assert _fit_table_widths((1000, 2000)) == (1000, 2000)
    for invalid in ((), (0, 100), (-10, 200), (1.5, 200), (True, 200)):
        with pytest.raises(ValueError):
            _fit_table_widths(invalid)


@pytest.mark.parametrize("widths", (
    (1, 1, 1_000_000),
    (1, 2, 10**100),
    (1, 1, 1, 10**40),
    (1,) * 20 + (10**30,),
))
def test_extreme_column_weight_ratio_never_exceeds_printable_width(
    widths: tuple[int, ...],
) -> None:
    fitted = _fit_table_widths(widths)
    assert len(fitted) == len(widths)
    assert all(isinstance(width, int) and width > 0 for width in fitted)
    assert sum(fitted) == _MAX_BODY_TABLE_WIDTH_TWIPS
    assert fitted[-1] == max(fitted)

    names = tuple(f"Column {index}" for index in range(len(widths)))
    document = ET.fromstring(
        '<root xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">'
        + _table(names, (names,), widths=widths) + "</root>"
    )
    table = document.find(W + "tbl")
    assert table is not None
    declared = int(table.find(W + "tblPr").find(W + "tblW").get(W + "w"))
    grid = tuple(int(col.get(W + "w")) for col in table.find(W + "tblGrid"))
    assert declared == sum(grid) == _MAX_BODY_TABLE_WIDTH_TWIPS
    for row in table.findall(W + "tr"):
        assert tuple(int(cell.find(W + "tcPr").find(W + "tcW").get(W + "w"))
                     for cell in row.findall(W + "tc")) == grid


def test_word_width_allocator_rejects_more_columns_than_positive_twips() -> None:
    with pytest.raises(ValueError, match="Too many columns"):
        _fit_table_widths((1,) * (_MAX_BODY_TABLE_WIDTH_TWIPS + 1))
