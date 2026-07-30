from __future__ import annotations

import pytest
from PySide6.QtWidgets import QApplication, QTabWidget

from geoworkbench.files.well_depth_reference import (
    DepthReferenceKind,
    calculate_well_depth_position,
)
from geoworkbench.ui.file_workspace_depth import FileWorkspaceWidget


def _application() -> QApplication:
    application = QApplication.instance()
    if application is None:
        application = QApplication([])
    return application


def test_vertical_well_position_uses_ground_and_documented_datum_height() -> None:
    result = calculate_well_depth_position(
        ground_elevation_msl_m=120.0,
        datum_height_above_ground_m=8.0,
        measured_depth_m=2_500.0,
        true_vertical_depth_m=2_500.0,
    )

    assert result.datum_elevation_msl_m == pytest.approx(128.0)
    assert result.bit_elevation_msl_m == pytest.approx(-2_372.0)
    assert result.true_vertical_depth_subsea_m == pytest.approx(2_372.0)
    assert result.bit_below_ground_m == pytest.approx(2_492.0)
    assert result.md_minus_tvd_m == pytest.approx(0.0)


def test_deviated_well_keeps_md_and_tvd_separate() -> None:
    result = calculate_well_depth_position(
        ground_elevation_msl_m=150.0,
        datum_height_above_ground_m=7.5,
        measured_depth_m=3_000.0,
        true_vertical_depth_m=2_500.0,
    )

    assert result.datum_elevation_msl_m == pytest.approx(157.5)
    assert result.bit_elevation_msl_m == pytest.approx(-2_342.5)
    assert result.md_minus_tvd_m == pytest.approx(500.0)


def test_tvd_cannot_exceed_md_for_the_same_datum() -> None:
    with pytest.raises(ValueError, match="TVD cannot exceed MD"):
        calculate_well_depth_position(
            ground_elevation_msl_m=100.0,
            datum_height_above_ground_m=8.0,
            measured_depth_m=1_000.0,
            true_vertical_depth_m=1_100.0,
        )


def test_depth_calculator_replaces_legacy_altitude_form_in_all_languages() -> None:
    _application()
    expected_tabs = {
        "ru": "Отметки и долото",
        "kk": "Белгілер және қашау",
        "en": "Elevations and bit",
    }
    for language, expected_tab in expected_tabs.items():
        widget = FileWorkspaceWidget(language=language)
        tabs = widget.findChild(QTabWidget, "petroleumCalculatorTabs")
        assert tabs is not None
        assert tabs.tabText(3) == expected_tab
        assert widget.findChild(type(widget), "wellDepthCalculator") is None
        legacy_group = widget.datum_inputs[0].parentWidget()
        assert legacy_group is not None and legacy_group.isHidden()
        widget.deleteLater()


def test_depth_calculator_reports_rt_and_bit_elevations() -> None:
    _application()
    widget = FileWorkspaceWidget(language="ru")
    rt_index = widget.depth_reference_kind.findData(DepthReferenceKind.RT)
    assert rt_index >= 0
    widget.depth_reference_kind.setCurrentIndex(rt_index)
    widget.depth_ground_elevation.setValue(150.0)
    widget.depth_datum_height.setValue(7.5)
    widget.depth_measured_depth.setValue(3_000.0)
    widget.depth_vertical_well.setChecked(False)
    widget.depth_true_vertical_depth.setValue(2_500.0)

    result = widget.depth_result.text()
    assert "157.500 m" in result
    assert "-2342.500 m" in result
    assert "500.000 m" in result
    widget.deleteLater()


def test_ground_level_reference_forces_zero_offset() -> None:
    _application()
    widget = FileWorkspaceWidget(language="en")
    gl_index = widget.depth_reference_kind.findData(DepthReferenceKind.GL)
    assert gl_index >= 0
    widget.depth_reference_kind.setCurrentIndex(gl_index)

    assert widget.depth_datum_height.value() == 0.0
    assert not widget.depth_datum_height.isEnabled()
    widget.deleteLater()
