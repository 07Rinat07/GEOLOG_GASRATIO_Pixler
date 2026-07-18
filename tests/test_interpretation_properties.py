from geoworkbench.domain.models import InterpretationInterval, WellInterpretation
from geoworkbench.services.localization import AppLanguage
from geoworkbench.ui.interpretation_properties import InterpretationPropertiesPanel


def test_interpretation_properties_panel_emits_edited_values(qapp) -> None:
    panel = InterpretationPropertiesPanel(language=AppLanguage.EN)
    interpretation = WellInterpretation("primary", "Primary")
    interval = InterpretationInterval(
        "interval",
        100.0,
        150.0,
        "Reservoir",
        "Sand A",
        "#fde68a",
        "Initial",
    )
    emitted: list[tuple[str, str, object]] = []
    panel.update_requested.connect(
        lambda interpretation_id, interval_id, values: emitted.append(
            (interpretation_id, interval_id, values)
        )
    )

    panel.show_interval(interpretation, interval)
    panel.bottom_input.setValue(145.0)
    panel.label_input.setText("Sand A1")
    panel.comment_input.setPlainText("Updated from property panel")
    panel.apply_button.click()

    assert panel.interpretation_label.text() == "Primary"
    assert emitted == [
        (
            "primary",
            "interval",
            {
                "top_depth": 100.0,
                "bottom_depth": 145.0,
                "interval_type": "Reservoir",
                "label": "Sand A1",
                "color": "#fde68a",
                "comment": "Updated from property panel",
            },
        )
    ]
    panel.clear()
    assert panel.form_widget.isHidden()
    assert panel.apply_button.isEnabled() is False
    panel.close()
