from PySide6.QtCore import Qt
from PySide6.QtTest import QTest

from geoworkbench.services.localization import AppLanguage
from geoworkbench.tablet.models import (
    CurveLineStyle,
    CurveStyle,
    TrackDefinition,
    TrackKind,
    XScale,
)
from geoworkbench.ui.track_inspector import TrackInspector


def test_inspector_emits_edited_track_settings(qapp) -> None:
    inspector = TrackInspector()
    track = TrackDefinition("curve", "Curve", TrackKind.CURVE, width=240)
    emitted: list[tuple[object, ...]] = []
    inspector.settings_requested.connect(lambda *args: emitted.append(args))
    inspector.show_track(track)
    inspector.width_input.setValue(360)
    inspector.scale_input.setCurrentIndex(
        inspector.scale_input.findData(XScale.LOGARITHMIC.value)
    )
    inspector.auto_range_input.setChecked(False)
    inspector.minimum_input.setValue(0.1)
    inspector.maximum_input.setValue(1000.0)

    QTest.mouseClick(inspector.apply_button, Qt.MouseButton.LeftButton)
    qapp.processEvents()

    assert emitted == [("curve", 360, "logarithmic", 0.1, 1000.0)]
    inspector.close()


def test_inspector_emits_none_for_automatic_range(qapp) -> None:
    inspector = TrackInspector()
    inspector.show_track(
        TrackDefinition(
            "curve",
            "Curve",
            TrackKind.CURVE,
            x_min=1.0,
            x_max=10.0,
        )
    )
    emitted: list[tuple[object, ...]] = []
    inspector.settings_requested.connect(lambda *args: emitted.append(args))
    inspector.auto_range_input.setChecked(True)

    QTest.mouseClick(inspector.apply_button, Qt.MouseButton.LeftButton)
    qapp.processEvents()

    assert emitted[0][-2:] == (None, None)
    assert inspector.minimum_input.isEnabled() is False
    inspector.close()


def test_inspector_uses_selected_language_without_changing_scale_values(qapp) -> None:
    inspector = TrackInspector(language=AppLanguage.EN)
    inspector.show_track(
        TrackDefinition(
            "curve",
            "Gamma Ray",
            TrackKind.CURVE,
            curve_mnemonics=["GR"],
        )
    )

    assert inspector.apply_button.text() == "Apply"
    assert inspector.scale_input.itemText(0) == "Linear"
    assert inspector.scale_input.itemData(0) == XScale.LINEAR.value
    assert inspector.scale_input.itemText(1) == "Logarithmic"
    assert "Type: curve" in inspector._summary.text()
    assert "Curves: GR" in inspector._summary.text()
    inspector.close()


def test_inspector_uses_data_range_when_switching_from_auto_to_manual(qapp) -> None:
    inspector = TrackInspector()
    inspector.show_track(
        TrackDefinition("curve", "Curve", TrackKind.CURVE),
        suggested_range=(-12.5, 87.25),
    )

    assert inspector.auto_range_input.isChecked() is True
    assert inspector.minimum_input.value() == -12.5
    assert inspector.maximum_input.value() == 87.25
    inspector.auto_range_input.setChecked(False)
    assert inspector.minimum_input.isEnabled() is True
    assert inspector.maximum_input.isEnabled() is True
    inspector.close()


def test_inspector_edits_selected_curve_style(qapp) -> None:
    inspector = TrackInspector(language=AppLanguage.EN)
    track = TrackDefinition(
        "gas",
        "Gas",
        TrackKind.GAS,
        curve_mnemonics=["C1", "C2"],
        curve_styles={"C2": CurveStyle("#00ff00", 3.0, CurveLineStyle.DOT)},
    )
    emitted: list[tuple[object, ...]] = []
    inspector.curve_style_requested.connect(lambda *args: emitted.append(args))
    inspector.show_track(track)
    inspector.curve_input.setCurrentText("C2")

    assert inspector.color_input.text() == "#00ff00"
    assert inspector.line_width_input.value() == 3.0
    inspector.color_input.setText("#112233")
    inspector.line_width_input.setValue(2.5)
    inspector.line_style_input.setCurrentIndex(
        inspector.line_style_input.findData(CurveLineStyle.DASH.value)
    )
    QTest.mouseClick(inspector.style_button, Qt.MouseButton.LeftButton)

    assert emitted == [("gas", "C2", "#112233", 2.5, "dash")]
    inspector.close()


def test_inspector_edits_track_grid(qapp) -> None:
    inspector = TrackInspector(language=AppLanguage.EN)
    track = TrackDefinition(
        "curve", "Curve", TrackKind.CURVE, grid_x=False, grid_y=True, grid_alpha=0.4
    )
    emitted: list[tuple[object, ...]] = []
    inspector.grid_requested.connect(lambda *args: emitted.append(args))

    inspector.show_track(track)

    assert inspector.grid_x_input.isChecked() is False
    assert inspector.grid_y_input.isChecked() is True
    assert inspector.grid_alpha_input.value() == 0.4
    inspector.grid_x_input.setChecked(True)
    inspector.grid_y_input.setChecked(False)
    inspector.grid_alpha_input.setValue(0.65)
    QTest.mouseClick(inspector.grid_button, Qt.MouseButton.LeftButton)

    assert emitted == [("curve", True, False, 0.65)]
    inspector.close()


def test_inspector_edits_x_axis_label(qapp) -> None:
    inspector = TrackInspector(language=AppLanguage.EN)
    track = TrackDefinition(
        "curve", "Curve", TrackKind.CURVE, x_axis_label="ROP, m/h"
    )
    emitted: list[tuple[object, ...]] = []
    inspector.x_axis_label_requested.connect(lambda *args: emitted.append(args))

    inspector.show_track(track)
    assert inspector.x_axis_label_input.text() == "ROP, m/h"
    inspector.x_axis_label_input.setText("  Rate  ")
    QTest.mouseClick(inspector.axis_label_button, Qt.MouseButton.LeftButton)

    assert emitted == [("curve", "Rate")]
    inspector.close()
