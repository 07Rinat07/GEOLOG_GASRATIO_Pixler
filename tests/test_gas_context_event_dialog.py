import numpy as np
from PySide6.QtCore import QLocale
from PySide6.QtWidgets import QDialogButtonBox, QPushButton, QTableWidget

from geoworkbench.domain.gas_context_events import GasContextEventType
from geoworkbench.domain.models import Dataset, DatasetKind, DepthDomain
from geoworkbench.project.session import ProjectSession
from geoworkbench.services.gas_context_event_editor import GasContextEventEditorController
from geoworkbench.services.localization import AppLanguage
from geoworkbench.ui.gas_context_event_dialog import GasContextEventDialog


def _session() -> ProjectSession:
    session = ProjectSession()
    session.add_dataset(
        Dataset(
            dataset_id="dataset",
            name="Well",
            kind=DatasetKind.GTI,
            depth_domain=DepthDomain.MD,
            depth=np.array([100.0, 150.0, 200.0]),
        )
    )
    session.dirty = False
    return session


def test_gas_context_dialog_add_duplicate_delete_and_save(qapp) -> None:
    session = _session()
    controller = GasContextEventEditorController(session)
    dialog = GasContextEventDialog(controller, language=AppLanguage.EN)
    try:
        index = dialog.type_input.findData(GasContextEventType.CONNECTION_GAS)
        dialog.type_input.setCurrentIndex(index)
        dialog.top_input.setValue(120.0)
        dialog.bottom_input.setValue(121.0)
        dialog.reported_total_input.setText("4.25")
        dialog.reported_unit_input.setText("%")
        dialog.confirmed_input.setChecked(True)
        dialog.comment_input.setText("Connection gas")

        dialog._add()
        assert dialog.table.rowCount() == 1
        assert session.current_well is not None
        assert session.current_well.gas_context_events == []

        dialog._duplicate()
        assert dialog.table.rowCount() == 2
        assert len({event.event_id for event in controller.list_events()}) == 2

        dialog._delete()
        assert dialog.table.rowCount() == 1

        dialog._save()
        assert len(session.current_well.gas_context_events) == 1
        event = session.current_well.gas_context_events[0]
        assert event.event_type is GasContextEventType.CONNECTION_GAS
        assert event.reported_total_gas == 4.25
        assert event.reported_unit == "%"
        assert event.confirmed is True
        assert session.dirty is True
    finally:
        dialog.close()


def test_gas_context_dialog_exposes_required_repeated_row_actions(qapp) -> None:
    dialog = GasContextEventDialog(
        GasContextEventEditorController(_session()),
        language=AppLanguage.RU,
    )
    try:
        table = dialog.findChild(QTableWidget, "gas-context-event-table")
        assert table is not None
        assert table.columnCount() == 9
        assert dialog.findChild(QPushButton, "gas-context-event-add") is not None
        assert dialog.findChild(QPushButton, "gas-context-event-duplicate") is not None
        assert dialog.findChild(QPushButton, "gas-context-event-delete") is not None
        buttons = dialog.findChild(QDialogButtonBox, "gas-context-event-buttons")
        assert buttons is not None
        assert buttons.button(QDialogButtonBox.StandardButton.Save).text() == "Сохранить"
    finally:
        dialog.close()



def test_gas_context_dialog_parses_tg_with_validator_locale(qapp) -> None:
    controller = GasContextEventEditorController(_session())
    dialog = GasContextEventDialog(controller, language=AppLanguage.RU)
    try:
        validator = dialog.reported_total_input.validator()
        assert validator is not None
        validator.setLocale(
            QLocale(QLocale.Language.Russian, QLocale.Country.Kazakhstan)
        )
        dialog.reported_total_input.setText("4,25")
        dialog.top_input.setValue(120.0)
        dialog.bottom_input.setValue(121.0)

        dialog._add()

        event = controller.list_events()[0]
        assert event.reported_total_gas == 4.25
    finally:
        dialog.close()


def test_gas_context_dialog_preserves_valid_high_precision_depth_on_update(qapp) -> None:
    controller = GasContextEventEditorController(_session())
    original = controller.add(
        event_type=GasContextEventType.CONNECTION_GAS,
        top_depth=123_456.123456789,
        bottom_depth=123_457.987654321,
        comment="before",
    )
    dialog = GasContextEventDialog(controller, language=AppLanguage.EN)
    try:
        dialog.comment_input.setText("after")
        dialog._update()

        updated = controller.get(original.event_id)
        assert updated.top_depth == original.top_depth
        assert updated.bottom_depth == original.bottom_depth
        assert updated.comment == "after"
    finally:
        dialog.close()
