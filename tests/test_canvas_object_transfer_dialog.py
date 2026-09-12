from __future__ import annotations

import pytest
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QDialogButtonBox, QMessageBox

from geoworkbench.domain.models import CanvasObject, Project, Well
from geoworkbench.project.canvas_object_transfer_controller import (
    CanvasObjectCollisionPolicy,
    CanvasObjectTransferController,
    CanvasObjectTransferError,
)
from geoworkbench.project.session import ProjectSession
from geoworkbench.services.localization import AppLanguage
from geoworkbench.ui.canvas_object_transfer_dialog import CanvasObjectTransferDialog


def _canvas(object_id: str) -> CanvasObject:
    return CanvasObject(
        object_id=object_id,
        object_type="annotation",
        anchor_type="depth",
        y=1200.0,
        track_id="geology",
        parameter_mnemonic="GR",
        properties={"text": object_id},
    )


def _controller(*, collision: bool = False) -> tuple[CanvasObjectTransferController, Well, Well]:
    source = Well(
        "source",
        "Source well",
        canvas_objects=[_canvas("drawing-a"), _canvas("drawing-b")],
    )
    target = Well(
        "target",
        "Target well",
        canvas_objects=[_canvas("drawing-a")] if collision else [],
    )
    session = ProjectSession(
        project=Project(
            "project",
            "Project",
            wells={source.well_id: source, target.well_id: target},
        ),
        current_well_id=target.well_id,
    )
    return CanvasObjectTransferController(session), source, target


def test_dialog_requires_explicit_selection_and_applies_reviewed_transfer(
    qapp,
    monkeypatch,
) -> None:
    controller, _source, target = _controller()
    messages: list[str] = []
    monkeypatch.setattr(
        QMessageBox,
        "information",
        lambda _parent, _title, text: messages.append(text),
    )
    dialog = CanvasObjectTransferDialog(
        controller,
        target.well_id,
        language=AppLanguage.RU,
    )
    ok = dialog.buttons.button(QDialogButtonBox.StandardButton.Ok)

    dialog._analyze()
    assert messages and "Выберите хотя бы один" in messages[-1]
    assert dialog.plan is None
    assert ok.isEnabled() is False

    choice = dialog.source_table.item(1, 0)
    choice.setCheckState(Qt.CheckState.Checked)
    dialog._analyze()

    assert dialog.plan is not None
    assert dialog.plan.copy_count == 1
    assert dialog.preview_table.rowCount() == 1
    assert ok.isEnabled() is True
    dialog._accept()

    assert dialog.outcome is not None
    assert dialog.outcome.copied_object_ids == ("drawing-b",)
    assert [item.object_id for item in target.canvas_objects] == ["drawing-b"]
    dialog.close()


def test_dialog_exposes_explicit_rename_policy_for_id_collision(qapp) -> None:
    controller, _source, target = _controller(collision=True)
    dialog = CanvasObjectTransferDialog(
        controller,
        target.well_id,
        language=AppLanguage.EN,
    )
    choice = dialog.source_table.item(0, 0)
    choice.setCheckState(Qt.CheckState.Checked)
    rename_index = dialog.collision_combo.findData(CanvasObjectCollisionPolicy.RENAME)
    assert rename_index >= 0
    dialog.collision_combo.setCurrentIndex(rename_index)

    dialog._analyze()

    assert dialog.plan is not None
    assert dialog.plan.collision_count == 1
    assert dialog.plan.items[0].target_object_id == "drawing-a-copy"
    assert "Copy with new ID" == dialog.preview_table.item(0, 3).text()
    dialog.reject()


def test_dialog_reject_consumes_preview_authorization(qapp) -> None:
    controller, _source, target = _controller()
    dialog = CanvasObjectTransferDialog(controller, target.well_id)
    dialog.source_table.item(0, 0).setCheckState(Qt.CheckState.Checked)
    dialog._analyze()
    plan = dialog.plan
    assert plan is not None

    dialog.reject()

    with pytest.raises(CanvasObjectTransferError, match="повторно просмотрите"):
        controller.apply(plan)


def test_dialog_disables_preview_when_no_source_well_has_drawings(qapp) -> None:
    target = Well("target", "Target")
    other = Well("other", "Other")
    session = ProjectSession(
        project=Project(
            "project",
            "Project",
            wells={target.well_id: target, other.well_id: other},
        ),
        current_well_id=target.well_id,
    )
    dialog = CanvasObjectTransferDialog(
        CanvasObjectTransferController(session),
        target.well_id,
    )

    assert dialog.source_combo.count() == 0
    assert dialog.preview_button.isEnabled() is False
    assert "Нет других скважин" in dialog.counts_label.text()
    dialog.close()
