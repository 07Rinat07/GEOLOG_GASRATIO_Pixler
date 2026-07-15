import csv
import zipfile

import numpy as np

from geoworkbench.data.selection_export import export_selection_excel, export_selection_text
from geoworkbench.domain.models import CurveData, CurveMetadata, Dataset, DatasetKind, DepthDomain


def make_dataset() -> Dataset:
    dataset = Dataset(
        "dataset",
        "Well data",
        DatasetKind.GTI,
        DepthDomain.MD,
        np.array([100.0, 101.0, 102.0, 103.0]),
    )
    dataset.curves["c1"] = CurveData(
        CurveMetadata("c1", "C1", "C1", "%", "Methane", dataset.dataset_id),
        np.array([1.0, 2.0, 3.0, 4.0]),
    )
    dataset.curves["rop"] = CurveData(
        CurveMetadata("rop", "ROP", "ROP", "m/h", "ROP", dataset.dataset_id),
        np.array([10.0, 20.0, 30.0, 40.0]),
    )
    return dataset


def test_text_export_contains_only_selected_interval_and_curves(tmp_path) -> None:
    target = tmp_path / "selection.txt"

    export_selection_text(
        make_dataset(), target, ["c1", "rop"], 101.0, 102.0, delimiter="\t"
    )

    with target.open(encoding="utf-8", newline="") as stream:
        rows = list(csv.reader(stream, delimiter="\t"))
    assert rows == [
        ["DEPTH [m]", "C1 [%]", "ROP [m/h]"],
        ["101", "2", "20"],
        ["102", "3", "30"],
    ]


def test_excel_export_is_valid_openxml_with_data_and_metadata_sheets(tmp_path) -> None:
    target = tmp_path / "selection.xlsx"

    export_selection_excel(make_dataset(), target, ["c1"], 101.0, 102.0)

    with zipfile.ZipFile(target) as archive:
        assert archive.testzip() is None
        workbook = archive.read("xl/workbook.xml").decode("utf-8")
        data_sheet = archive.read("xl/worksheets/sheet1.xml").decode("utf-8")
        metadata_sheet = archive.read("xl/worksheets/sheet2.xml").decode("utf-8")
    assert 'name="Data"' in workbook
    assert 'name="Metadata"' in workbook
    assert "DEPTH [m]" in data_sheet
    assert "C1 [%]" in data_sheet
    assert "Well data" in metadata_sheet
