from __future__ import annotations

from PySide6.QtWidgets import (
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from geoworkbench.domain.models import (
    Dataset,
    IndexRole,
    TimeDepthAggregationPolicy,
)
from geoworkbench.project.time_depth_mapping_controller import TimeDepthMappingController
from geoworkbench.services.localization import AppLanguage


_TEXT = {
    AppLanguage.RU: {
        "title": "TIME↔DEPTH профили",
        "saved": "Сохранённые профили",
        "new": "Новый профиль",
        "name": "Имя",
        "time": "TIME индекс",
        "depth": "DEPTH индекс",
        "policy": "Повторные проходы",
        "save": "Сохранить",
        "delete": "Удалить",
        "value": "Время для проверки",
        "resolve": "Определить глубину",
        "close": "Закрыть",
        "empty": "Новый профиль",
        "result": "Глубина: {depth:g}; строка: {row}; совпадений: {count}; расстояние: {distance:g}",
    },
    AppLanguage.EN: {
        "title": "TIME↔DEPTH profiles",
        "saved": "Saved profiles",
        "new": "New profile",
        "name": "Name",
        "time": "TIME index",
        "depth": "DEPTH index",
        "policy": "Repeated passes",
        "save": "Save",
        "delete": "Delete",
        "value": "Time to test",
        "resolve": "Resolve depth",
        "close": "Close",
        "empty": "New profile",
        "result": "Depth: {depth:g}; row: {row}; matches: {count}; distance: {distance:g}",
    },
    AppLanguage.KK: {
        "title": "TIME↔DEPTH профильдері",
        "saved": "Сақталған профильдер",
        "new": "Жаңа профиль",
        "name": "Атауы",
        "time": "TIME индексі",
        "depth": "DEPTH индексі",
        "policy": "Қайталама өтулер",
        "save": "Сақтау",
        "delete": "Жою",
        "value": "Тексеру уақыты",
        "resolve": "Тереңдікті анықтау",
        "close": "Жабу",
        "empty": "Жаңа профиль",
        "result": "Тереңдік: {depth:g}; жол: {row}; сәйкестік: {count}; қашықтық: {distance:g}",
    },
}


class TimeDepthMappingDialog(QDialog):
    def __init__(
        self,
        dataset: Dataset,
        controller: TimeDepthMappingController,
        parent: QWidget | None = None,
        *,
        language: AppLanguage = AppLanguage.RU,
    ) -> None:
        super().__init__(parent)
        self.dataset = dataset
        self.controller = controller
        self.text = _TEXT[language]
        self.setWindowTitle(self.text["title"])
        self.resize(560, 360)

        root = QVBoxLayout(self)
        form = QFormLayout()
        self.profile_selector = QComboBox()
        self.profile_selector.setObjectName("time-depth-profile-selector")
        form.addRow(self.text["saved"], self.profile_selector)
        self.name_edit = QLineEdit()
        self.name_edit.setObjectName("time-depth-profile-name")
        form.addRow(self.text["name"], self.name_edit)
        self.time_selector = QComboBox()
        self.depth_selector = QComboBox()
        for index in dataset.indexes.values():
            label = f"{index.mnemonic} [{index.unit or '—'}] · {index.index_id}"
            if index.role is IndexRole.TIME:
                self.time_selector.addItem(label, index.index_id)
            elif index.role is IndexRole.DEPTH:
                self.depth_selector.addItem(label, index.index_id)
        form.addRow(self.text["time"], self.time_selector)
        form.addRow(self.text["depth"], self.depth_selector)
        self.policy_selector = QComboBox()
        for policy in TimeDepthAggregationPolicy:
            self.policy_selector.addItem(policy.value, policy)
        form.addRow(self.text["policy"], self.policy_selector)
        root.addLayout(form)

        profile_buttons = QHBoxLayout()
        self.save_button = QPushButton(self.text["save"])
        self.delete_button = QPushButton(self.text["delete"])
        profile_buttons.addWidget(self.save_button)
        profile_buttons.addWidget(self.delete_button)
        root.addLayout(profile_buttons)

        resolve_form = QFormLayout()
        self.time_value_edit = QLineEdit()
        self.time_value_edit.setObjectName("time-depth-test-value")
        resolve_form.addRow(self.text["value"], self.time_value_edit)
        root.addLayout(resolve_form)
        self.resolve_button = QPushButton(self.text["resolve"])
        self.result_label = QLabel()
        self.result_label.setObjectName("time-depth-result")
        root.addWidget(self.resolve_button)
        root.addWidget(self.result_label)
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Close)
        buttons.button(QDialogButtonBox.StandardButton.Close).setText(self.text["close"])
        buttons.rejected.connect(self.reject)
        root.addWidget(buttons)

        self.profile_selector.currentIndexChanged.connect(self._load_profile)
        self.save_button.clicked.connect(self._save)
        self.delete_button.clicked.connect(self._delete)
        self.resolve_button.clicked.connect(self._resolve)
        self._refresh_profiles()

    def _refresh_profiles(self, selected_id: str | None = None) -> None:
        self.profile_selector.blockSignals(True)
        self.profile_selector.clear()
        self.profile_selector.addItem(self.text["empty"], None)
        profiles = sorted(
            (
                profile
                for profile in self.controller.session.project.time_depth_mapping_profiles.values()
                if profile.dataset_id == self.dataset.dataset_id
            ),
            key=lambda profile: profile.name.casefold(),
        )
        for profile in profiles:
            self.profile_selector.addItem(profile.name, profile.profile_id)
        if selected_id is not None:
            index = self.profile_selector.findData(selected_id)
            self.profile_selector.setCurrentIndex(max(index, 0))
        self.profile_selector.blockSignals(False)
        self._load_profile()

    def _load_profile(self) -> None:
        profile_id = self.profile_selector.currentData()
        self.delete_button.setEnabled(profile_id is not None)
        self.resolve_button.setEnabled(profile_id is not None)
        if profile_id is None:
            self.name_edit.clear()
            self.result_label.clear()
            return
        profile = self.controller.session.project.time_depth_mapping_profiles[profile_id]
        self.name_edit.setText(profile.name)
        self.time_selector.setCurrentIndex(self.time_selector.findData(profile.time_index_id))
        self.depth_selector.setCurrentIndex(self.depth_selector.findData(profile.depth_index_id))
        self.policy_selector.setCurrentIndex(
            self.policy_selector.findData(profile.aggregation_policy.value)
        )

    def _save(self) -> None:
        try:
            profile = self.controller.save_profile(
                self.name_edit.text(),
                str(self.time_selector.currentData()),
                str(self.depth_selector.currentData()),
                TimeDepthAggregationPolicy(str(self.policy_selector.currentData())),
            )
        except (RuntimeError, ValueError) as exc:
            QMessageBox.warning(self, self.text["title"], str(exc))
            return
        self._refresh_profiles(profile.profile_id)

    def _delete(self) -> None:
        profile_id = self.profile_selector.currentData()
        if profile_id is None:
            return
        answer = QMessageBox.question(self, self.text["title"], self.text["delete"] + "?")
        if answer != QMessageBox.StandardButton.Yes:
            return
        self.controller.delete_profile(profile_id)
        self._refresh_profiles()

    def _resolve(self) -> None:
        profile_id = self.profile_selector.currentData()
        if profile_id is None:
            return
        try:
            match = self.controller.resolve(profile_id, self.time_value_edit.text())
        except (KeyError, ValueError) as exc:
            QMessageBox.warning(self, self.text["title"], str(exc))
            return
        self.result_label.setText(
            self.text["result"].format(
                depth=match.depth,
                row="—" if match.row is None else match.row + 1,
                count=len(match.matched_rows),
                distance=match.distance,
            )
        )
