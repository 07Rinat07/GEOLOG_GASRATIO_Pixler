import numpy as np

from geoworkbench.domain.models import (
    CurveData,
    CurveMetadata,
    Dataset,
    DatasetKind,
    DepthDomain,
)
from geoworkbench.ui.las_curve_browser import LasCurveBrowser


def make_dataset() -> Dataset:
    dataset = Dataset(
        "dataset",
        "LAS",
        DatasetKind.GTI,
        DepthDomain.MD,
        np.array([1.0, 2.0, 3.0]),
    )
    for mnemonic, unit, description, values in (
        ("C1", "%", "Methane", [1.0, 2.0, 3.0]),
        ("BIT_RPM", "rpm", "Bit rotation", [100.0, 110.0, 120.0]),
        ("EMPTY", "", "No data", [np.nan, np.nan, np.nan]),
    ):
        curve_id = f"curve-{mnemonic}"
        dataset.curves[curve_id] = CurveData(
            CurveMetadata(
                curve_id,
                mnemonic,
                mnemonic,
                unit,
                description,
                dataset.dataset_id,
            ),
            np.asarray(values, dtype=float),
        )
    return dataset


def test_curve_browser_shows_metadata_and_recommended_selection(qapp) -> None:
    browser = LasCurveBrowser()
    browser.set_dataset(make_dataset())

    assert browser.tree.topLevelItemCount() == 3
    browser.select_recommended()

    assert set(browser.selected_mnemonics()) == {"C1", "BIT_RPM"}
    assert "2 из 3" in browser.summary.text()
    empty = next(
        browser.tree.topLevelItem(index)
        for index in range(browser.tree.topLevelItemCount())
        if browser.tree.topLevelItem(index).text(0) == "EMPTY"
    )
    assert empty.isDisabled()
    browser.close()


def test_curve_browser_filters_by_description(qapp) -> None:
    browser = LasCurveBrowser()
    browser.set_dataset(make_dataset())

    browser.search_input.setText("rotation")

    visible = [
        browser.tree.topLevelItem(index).text(0)
        for index in range(browser.tree.topLevelItemCount())
        if not browser.tree.topLevelItem(index).isHidden()
    ]
    assert visible == ["BIT_RPM"]
    browser.close()


def test_curve_browser_shows_canonical_mnemonic_and_reference_range(qapp) -> None:
    browser = LasCurveBrowser()
    browser.set_dataset(make_dataset())

    c1 = next(
        browser.tree.topLevelItem(index)
        for index in range(browser.tree.topLevelItemCount())
        if browser.tree.topLevelItem(index).text(0) == "C1"
    )

    assert browser.tree.columnCount() == 8
    assert c1.text(1) == "C1"
    assert c1.text(6) != "—"
    assert "Sensors.DB" in c1.toolTip(0)
    browser.close()
