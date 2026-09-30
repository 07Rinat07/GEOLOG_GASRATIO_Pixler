from __future__ import annotations

import importlib.util

import pytest


pytestmark = pytest.mark.skipif(
    importlib.util.find_spec("PySide6") is None,
    reason="PySide6 is not installed in the headless test environment",
)


def test_alarm_settings_editor_creates_updates_and_removes_rules(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("QT_QPA_PLATFORM", "offscreen")
    from PySide6.QtWidgets import QApplication

    from geoworkbench.services.localization import AppLanguage
    from geoworkbench.ui.wits0_alarm_settings_editor import Wits0AlarmSettingsEditor

    app = QApplication.instance() or QApplication([])
    editor = Wits0AlarmSettingsEditor(language=AppLanguage.RU)
    changes: list[tuple[object, ...]] = []
    editor.rulesChanged.connect(lambda: changes.append(editor.rules()))

    try:
        editor.set_channels((("total_gas", "%"), ("spp", "bar")))
        assert editor.channel_combo.count() == 2
        assert editor.apply_button.isEnabled()

        editor.minimum_check.setChecked(True)
        editor.minimum_spin.setValue(1.5)
        editor.maximum_check.setChecked(True)
        editor.maximum_spin.setValue(8.5)
        editor.hysteresis_spin.setValue(0.4)
        editor.debounce_spin.setValue(3)
        editor.visual_check.setChecked(True)
        editor.audio_check.setChecked(True)
        editor.apply_button.click()

        rules = editor.rules()
        assert len(rules) == 1
        assert rules[0].mnemonic == "total_gas"
        assert rules[0].minimum == pytest.approx(1.5)
        assert rules[0].maximum == pytest.approx(8.5)
        assert rules[0].hysteresis == pytest.approx(0.4)
        assert rules[0].debounce_samples == 3
        assert rules[0].visual_enabled
        assert rules[0].audio_enabled
        assert editor.remove_button.isEnabled()

        editor.maximum_spin.setValue(9.0)
        editor.apply_button.click()
        rules = editor.rules()
        assert len(rules) == 1
        assert rules[0].maximum == pytest.approx(9.0)

        editor.remove_button.click()
        assert editor.rules() == ()
        assert not editor.remove_button.isEnabled()
        assert len(changes) == 3
    finally:
        editor.close()
        app.processEvents()


def test_alarm_settings_editor_rejects_missing_or_inverted_thresholds(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("QT_QPA_PLATFORM", "offscreen")
    from PySide6.QtWidgets import QApplication

    from geoworkbench.services.localization import AppLanguage
    from geoworkbench.ui.wits0_alarm_settings_editor import Wits0AlarmSettingsEditor

    app = QApplication.instance() or QApplication([])
    editor = Wits0AlarmSettingsEditor(language=AppLanguage.EN)

    try:
        editor.set_channels((("total_gas", "%"),))
        editor.apply_button.click()
        assert editor.rules() == ()
        assert "Invalid rule" in editor.status_label.text()

        editor.minimum_check.setChecked(True)
        editor.minimum_spin.setValue(10.0)
        editor.maximum_check.setChecked(True)
        editor.maximum_spin.setValue(5.0)
        editor.apply_button.click()
        assert editor.rules() == ()
        assert "Invalid rule" in editor.status_label.text()
    finally:
        editor.close()
        app.processEvents()


def test_alarm_settings_editor_restores_saved_rule_by_normalized_mnemonic(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("QT_QPA_PLATFORM", "offscreen")
    from PySide6.QtWidgets import QApplication

    from geoworkbench.acquisition.wits0_live_forms import Wits0SavedAlarmRule
    from geoworkbench.services.localization import AppLanguage
    from geoworkbench.ui.wits0_alarm_settings_editor import Wits0AlarmSettingsEditor

    app = QApplication.instance() or QApplication([])
    editor = Wits0AlarmSettingsEditor(language=AppLanguage.KK)

    try:
        editor.set_channels((("TOTAL-GAS", "%"),))
        editor.set_rules(
            (
                Wits0SavedAlarmRule(
                    mnemonic="total_gas",
                    maximum=4.0,
                    hysteresis=0.2,
                    debounce_samples=2,
                ),
            )
        )

        assert editor.maximum_check.isChecked()
        assert editor.maximum_spin.value() == pytest.approx(4.0)
        assert editor.hysteresis_spin.value() == pytest.approx(0.2)
        assert editor.debounce_spin.value() == 2
        assert editor.remove_button.isEnabled()
    finally:
        editor.close()
        app.processEvents()
