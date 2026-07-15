from PySide6.QtCore import Qt
from PySide6.QtTest import QTest

from geoworkbench.services.localization import AppLanguage
from geoworkbench.tablet.models import TrackDefinition, TrackKind, XScale
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
