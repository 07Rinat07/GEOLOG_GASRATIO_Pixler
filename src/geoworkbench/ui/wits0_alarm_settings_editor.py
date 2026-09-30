from __future__ import annotations

from collections.abc import Iterable

from PySide6.QtCore import Signal
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDoubleSpinBox,
    QGridLayout,
    QGroupBox,
    QLabel,
    QPushButton,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)

from geoworkbench.acquisition.wits0_live_forms import Wits0SavedAlarmRule
from geoworkbench.catalogs.sensors import normalize_sensor_key
from geoworkbench.services.localization import AppLanguage


class Wits0AlarmSettingsEditor(QGroupBox):
    """Edit persisted per-channel WITS alarm rules without runtime alarm state."""

    rulesChanged = Signal()

    def __init__(
        self,
        parent: QWidget | None = None,
        *,
        language: AppLanguage = AppLanguage.RU,
    ) -> None:
        super().__init__(_text(language, "group"), parent)
        self.setObjectName("wits0AlarmSettingsEditor")
        self._language = language
        self._rules: dict[str, Wits0SavedAlarmRule] = {}
        self._updating = False

        root = QVBoxLayout(self)
        grid = QGridLayout()
        grid.setHorizontalSpacing(6)
        grid.setVerticalSpacing(4)

        grid.addWidget(QLabel(_text(language, "channel"), self), 0, 0)
        self.channel_combo = QComboBox(self)
        self.channel_combo.setObjectName("wits0AlarmChannelCombo")
        self.channel_combo.currentIndexChanged.connect(self._channel_changed)
        grid.addWidget(self.channel_combo, 0, 1, 1, 3)

        self.minimum_check = QCheckBox(_text(language, "minimum"), self)
        self.minimum_check.setObjectName("wits0AlarmMinimumCheck")
        self.minimum_check.toggled.connect(self.minimum_spin.setEnabled if hasattr(self, "minimum_spin") else lambda _v: None)
        grid.addWidget(self.minimum_check, 1, 0)
        self.minimum_spin = _value_spin(self, "wits0AlarmMinimumSpin")
        self.minimum_spin.setEnabled(False)
        self.minimum_check.toggled.connect(self.minimum_spin.setEnabled)
        grid.addWidget(self.minimum_spin, 1, 1)

        self.maximum_check = QCheckBox(_text(language, "maximum"), self)
        self.maximum_check.setObjectName("wits0AlarmMaximumCheck")
        grid.addWidget(self.maximum_check, 1, 2)
        self.maximum_spin = _value_spin(self, "wits0AlarmMaximumSpin")
        self.maximum_spin.setEnabled(False)
        self.maximum_check.toggled.connect(self.maximum_spin.setEnabled)
        grid.addWidget(self.maximum_spin, 1, 3)

        grid.addWidget(QLabel(_text(language, "hysteresis"), self), 2, 0)
        self.hysteresis_spin = _value_spin(self, "wits0AlarmHysteresisSpin")
        self.hysteresis_spin.setRange(0.0, 1.0e15)
        self.hysteresis_spin.setValue(0.0)
        grid.addWidget(self.hysteresis_spin, 2, 1)

        grid.addWidget(QLabel(_text(language, "debounce"), self), 2, 2)
        self.debounce_spin = QSpinBox(self)
        self.debounce_spin.setObjectName("wits0AlarmDebounceSpin")
        self.debounce_spin.setRange(1, 10_000)
        self.debounce_spin.setValue(1)
        grid.addWidget(self.debounce_spin, 2, 3)

        self.visual_check = QCheckBox(_text(language, "visual"), self)
        self.visual_check.setObjectName("wits0AlarmVisualCheck")
        self.visual_check.setChecked(True)
        grid.addWidget(self.visual_check, 3, 0, 1, 2)

        self.audio_check = QCheckBox(_text(language, "audio"), self)
        self.audio_check.setObjectName("wits0AlarmAudioCheck")
        grid.addWidget(self.audio_check, 3, 2, 1, 2)
        root.addLayout(grid)

        actions = QGridLayout()
        self.apply_button = QPushButton(_text(language, "apply"), self)
        self.apply_button.setObjectName("wits0AlarmApplyButton")
        self.apply_button.clicked.connect(self._apply_current)
        actions.addWidget(self.apply_button, 0, 0)
        self.remove_button = QPushButton(_text(language, "remove"), self)
        self.remove_button.setObjectName("wits0AlarmRemoveButton")
        self.remove_button.clicked.connect(self._remove_current)
        actions.addWidget(self.remove_button, 0, 1)
        actions.setColumnStretch(0, 1)
        actions.setColumnStretch(1, 1)
        root.addLayout(actions)

        self.status_label = QLabel("", self)
        self.status_label.setObjectName("wits0AlarmStatusLabel")
        self.status_label.setWordWrap(True)
        root.addWidget(self.status_label)
        self._sync_enabled_state()

    def set_channels(self, channels: Iterable[tuple[str, str | None]]) -> None:
        current = self.current_mnemonic()
        unique: dict[str, tuple[str, str | None]] = {}
        for mnemonic, unit in channels:
            key = normalize_sensor_key(mnemonic)
            if key and key not in unique:
                unique[key] = (mnemonic.strip(), unit.strip() if unit else None)

        self._updating = True
        try:
            self.channel_combo.clear()
            for key, (mnemonic, unit) in unique.items():
                label = f"{mnemonic} [{unit}]" if unit else mnemonic
                self.channel_combo.addItem(label, (key, mnemonic))
            target = -1
            if current:
                current_key = normalize_sensor_key(current)
                for index in range(self.channel_combo.count()):
                    data = self.channel_combo.itemData(index)
                    if isinstance(data, tuple) and data[0] == current_key:
                        target = index
                        break
            if target >= 0:
                self.channel_combo.setCurrentIndex(target)
        finally:
            self._updating = False
        self._load_current_rule()

    def set_rules(self, rules: Iterable[Wits0SavedAlarmRule]) -> None:
        self._rules = {
            normalize_sensor_key(rule.mnemonic): rule
            for rule in rules
            if normalize_sensor_key(rule.mnemonic)
        }
        self._load_current_rule()

    def rules(self) -> tuple[Wits0SavedAlarmRule, ...]:
        return tuple(self._rules[key] for key in sorted(self._rules))

    def clear_rules(self) -> None:
        self._rules.clear()
        self._load_current_rule()
        self.rulesChanged.emit()

    def current_mnemonic(self) -> str | None:
        data = self.channel_combo.currentData()
        if not isinstance(data, tuple) or len(data) != 2:
            return None
        mnemonic = data[1]
        return mnemonic if isinstance(mnemonic, str) and mnemonic.strip() else None

    def _channel_changed(self, _index: int) -> None:
        if not self._updating:
            self._load_current_rule()

    def _load_current_rule(self) -> None:
        mnemonic = self.current_mnemonic()
        rule = (
            self._rules.get(normalize_sensor_key(mnemonic))
            if mnemonic is not None
            else None
        )
        self._updating = True
        try:
            self.minimum_check.setChecked(rule is not None and rule.minimum is not None)
            self.maximum_check.setChecked(rule is not None and rule.maximum is not None)
            self.minimum_spin.setValue(rule.minimum if rule and rule.minimum is not None else 0.0)
            self.maximum_spin.setValue(rule.maximum if rule and rule.maximum is not None else 0.0)
            self.hysteresis_spin.setValue(rule.hysteresis if rule else 0.0)
            self.debounce_spin.setValue(rule.debounce_samples if rule else 1)
            self.visual_check.setChecked(rule.visual_enabled if rule else True)
            self.audio_check.setChecked(rule.audio_enabled if rule else False)
            self.status_label.setText(
                _text(self._language, "configured") if rule is not None else ""
            )
        finally:
            self._updating = False
        self.minimum_spin.setEnabled(self.minimum_check.isChecked())
        self.maximum_spin.setEnabled(self.maximum_check.isChecked())
        self._sync_enabled_state()

    def _apply_current(self) -> None:
        mnemonic = self.current_mnemonic()
        if mnemonic is None:
            return
        minimum = float(self.minimum_spin.value()) if self.minimum_check.isChecked() else None
        maximum = float(self.maximum_spin.value()) if self.maximum_check.isChecked() else None
        try:
            rule = Wits0SavedAlarmRule(
                mnemonic=mnemonic,
                minimum=minimum,
                maximum=maximum,
                hysteresis=float(self.hysteresis_spin.value()),
                debounce_samples=int(self.debounce_spin.value()),
                visual_enabled=self.visual_check.isChecked(),
                audio_enabled=self.audio_check.isChecked(),
            )
        except ValueError as exc:
            self.status_label.setText(
                _text(self._language, "invalid").format(error=str(exc))
            )
            return
        self._rules[normalize_sensor_key(mnemonic)] = rule
        self.status_label.setText(_text(self._language, "configured"))
        self.remove_button.setEnabled(True)
        self.rulesChanged.emit()

    def _remove_current(self) -> None:
        mnemonic = self.current_mnemonic()
        if mnemonic is None:
            return
        key = normalize_sensor_key(mnemonic)
        if self._rules.pop(key, None) is not None:
            self.rulesChanged.emit()
        self._load_current_rule()

    def _sync_enabled_state(self) -> None:
        has_channel = self.channel_combo.count() > 0
        for widget in (
            self.minimum_check,
            self.maximum_check,
            self.hysteresis_spin,
            self.debounce_spin,
            self.visual_check,
            self.audio_check,
            self.apply_button,
        ):
            widget.setEnabled(has_channel)
        mnemonic = self.current_mnemonic()
        self.remove_button.setEnabled(
            mnemonic is not None
            and normalize_sensor_key(mnemonic) in self._rules
        )


def _value_spin(parent: QWidget, object_name: str) -> QDoubleSpinBox:
    spin = QDoubleSpinBox(parent)
    spin.setObjectName(object_name)
    spin.setDecimals(6)
    spin.setRange(-1.0e15, 1.0e15)
    spin.setKeyboardTracking(False)
    return spin


def _text(language: AppLanguage, key: str) -> str:
    translations = {
        AppLanguage.RU: {
            "group": "Тревоги параметров",
            "channel": "Параметр",
            "minimum": "Мин.",
            "maximum": "Макс.",
            "hysteresis": "Гистерезис",
            "debounce": "Подтверждение, отсчётов",
            "visual": "Визуальная тревога",
            "audio": "Звуковая тревога",
            "apply": "Применить правило",
            "remove": "Удалить правило",
            "configured": "Правило настроено; сохраните форму.",
            "invalid": "Некорректное правило: {error}",
        },
        AppLanguage.KK: {
            "group": "Параметр дабылдары",
            "channel": "Параметр",
            "minimum": "Мин.",
            "maximum": "Макс.",
            "hysteresis": "Гистерезис",
            "debounce": "Растау, есеп саны",
            "visual": "Көрнекі дабыл",
            "audio": "Дыбыстық дабыл",
            "apply": "Ережені қолдану",
            "remove": "Ережені жою",
            "configured": "Ереже бапталды; пішінді сақтаңыз.",
            "invalid": "Ереже қате: {error}",
        },
        AppLanguage.EN: {
            "group": "Parameter alarms",
            "channel": "Parameter",
            "minimum": "Min",
            "maximum": "Max",
            "hysteresis": "Hysteresis",
            "debounce": "Confirm samples",
            "visual": "Visual alarm",
            "audio": "Audio alarm",
            "apply": "Apply rule",
            "remove": "Remove rule",
            "configured": "Rule configured; save the form.",
            "invalid": "Invalid rule: {error}",
        },
    }
    return translations.get(language, translations[AppLanguage.EN]).get(key, key)


__all__ = ["Wits0AlarmSettingsEditor"]
