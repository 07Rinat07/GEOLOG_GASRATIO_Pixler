from __future__ import annotations

import pytest
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QDialogButtonBox, QMessageBox

from geoworkbench.domain.models import CanvasObject, Project, Well
from geoworkbench.project.canvas_object_transfer_controller import (
    CanvasObjectCollisionPolicy,
    CanvasObjectTransferController,
    CanvasObjectTransferError,
    CanvasObjectTransferErrorReason,
)
from geoworkbench.project.session import ProjectSession
from geoworkbench.services.localization import AppLanguage
from geoworkbench.ui.canvas_object_transfer_dialog import CanvasObjectTransferDialog


@pytest.fixture(autouse=True)
def fail_on_unexpected_message_box(monkeypatch) -> None:
    """Report unexpected modal dialogs instead of blocking a headless CI job."""
    def unexpected_message(_parent, _title, text):
        pytest.fail(f"Unexpected message box: {text}")

    for method in ("information", "warning", "critical"):
        monkeypatch.setattr(QMessageBox, method, unexpected_message)


def _canvas(object_id: str) -> CanvasObject:
    return CanvasObject(
        object_id=object_id,
        object_type="annotation",
        anchor_type="depth",
        x=10.0,
        y=1200.0,
        width=24.0,
        height=12.0,
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


def test_selection_change_invalidates_reviewed_plan(qapp) -> None:
    controller, _source, target = _controller()
    dialog = CanvasObjectTransferDialog(controller, target.well_id)
    ok = dialog.buttons.button(QDialogButtonBox.StandardButton.Ok)
    dialog.source_table.item(0, 0).setCheckState(Qt.CheckState.Checked)
    dialog._analyze()
    reviewed_plan = dialog.plan

    assert reviewed_plan is not None
    assert ok.isEnabled() is True
    assert dialog.preview_table.rowCount() == 1

    dialog.source_table.item(1, 0).setCheckState(Qt.CheckState.Checked)

    assert dialog.plan is None
    assert dialog.preview_table.rowCount() == 0
    assert ok.isEnabled() is False
    with pytest.raises(CanvasObjectTransferError, match="повторно просмотрите"):
        controller.apply(reviewed_plan)
    dialog.close()


@pytest.mark.parametrize("policy", list(CanvasObjectCollisionPolicy))
def test_dialog_decodes_string_policy_from_qt(qapp, policy) -> None:
    controller, _source, target = _controller()
    dialog = CanvasObjectTransferDialog(controller, target.well_id)
    dialog.source_table.item(0, 0).setCheckState(Qt.CheckState.Checked)
    index = dialog.collision_combo.findData(policy.value)
    assert index >= 0
    dialog.collision_combo.setCurrentIndex(index)

    dialog._analyze()

    assert dialog.plan is not None
    assert dialog.plan.collision_policy is policy
    dialog.reject()


@pytest.mark.parametrize("invalid_policy", [None, "unknown-policy", 42])
def test_dialog_rejects_invalid_policy_without_transfer(qapp, monkeypatch, invalid_policy) -> None:
    controller, _source, target = _controller()
    dialog = CanvasObjectTransferDialog(controller, target.well_id)
    dialog.source_table.item(0, 0).setCheckState(Qt.CheckState.Checked)
    dialog._analyze()
    reviewed_plan = dialog.plan
    assert reviewed_plan is not None
    warnings: list[str] = []
    monkeypatch.setattr(
        QMessageBox, "warning", lambda _parent, _title, text: warnings.append(text)
    )
    dialog.collision_combo.setItemData(dialog.collision_combo.currentIndex(), invalid_policy)

    dialog._analyze()
    dialog._accept()

    assert warnings == ["Не выбрана политика конфликтов ID."]
    assert dialog.plan is None
    assert not dialog.buttons.button(QDialogButtonBox.StandardButton.Ok).isEnabled()
    assert target.canvas_objects == []
    with pytest.raises(CanvasObjectTransferError, match="повторно просмотрите"):
        controller.apply(reviewed_plan)
    dialog.reject()


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


def test_dialog_localizes_collision_error_in_english(qapp, monkeypatch) -> None:
    controller, _source, target = _controller(collision=True)
    warnings: list[str] = []
    monkeypatch.setattr(
        QMessageBox,
        "warning",
        lambda _parent, _title, text: warnings.append(text),
    )
    dialog = CanvasObjectTransferDialog(
        controller,
        target.well_id,
        language=AppLanguage.EN,
    )
    dialog.source_table.item(0, 0).setCheckState(Qt.CheckState.Checked)

    dialog._analyze()

    assert dialog.plan is None
    assert warnings
    assert "already exists in the target well" in warnings[-1]
    assert "drawing-a" in warnings[-1]
    assert "Рисунок" not in warnings[-1]
    dialog.close()


def test_dialog_localizes_stale_target_error_in_kazakh(qapp, monkeypatch) -> None:
    controller, _source, target = _controller()
    warnings: list[str] = []
    monkeypatch.setattr(
        QMessageBox,
        "warning",
        lambda _parent, _title, text: warnings.append(text),
    )
    dialog = CanvasObjectTransferDialog(
        controller,
        target.well_id,
        language=AppLanguage.KK,
    )
    dialog.source_table.item(0, 0).setCheckState(Qt.CheckState.Checked)
    dialog._analyze()
    assert dialog.plan is not None
    target.content_revision += 1

    dialog._accept()

    assert dialog.plan is None
    assert warnings
    assert "Мақсатты ұңғымадағы" in warnings[-1]
    assert "Рисунки" not in warnings[-1]
    dialog.close()


def test_dialog_never_leaks_raw_russian_for_structured_english_errors(qapp) -> None:
    controller, _source, target = _controller()
    dialog = CanvasObjectTransferDialog(
        controller,
        target.well_id,
        language=AppLanguage.EN,
    )
    reasons = (
        CanvasObjectTransferErrorReason.REVIEW_REQUIRED,
        CanvasObjectTransferErrorReason.SOURCE_CHANGED,
        CanvasObjectTransferErrorReason.TARGET_CHANGED,
        CanvasObjectTransferErrorReason.PACKAGE_REQUIRED,
        CanvasObjectTransferErrorReason.PERSISTENCE_FAILED,
        CanvasObjectTransferErrorReason.GENERAL,
    )

    for reason in reasons:
        message = dialog._error_text(
            CanvasObjectTransferError("Русский внутренний текст", reason=reason)
        )
        assert "Русский" not in message
        assert message
    dialog.close()


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



def test_canvas_transfer_dialog_fits_work_area_with_sticky_actions(qapp) -> None:
    controller, _source, target = _controller()
    dialog = CanvasObjectTransferDialog(
        controller,
        target.well_id,
        language=AppLanguage.EN,
    )
    try:
        screen = dialog.screen()
        assert screen is not None
        available = screen.availableGeometry()
        assert dialog.minimumWidth() <= dialog.width() <= available.width()
        assert dialog.minimumHeight() <= dialog.height() <= available.height()
        assert dialog.body_scroll.objectName() == "canvas-transfer-scroll"
        assert not dialog.body_scroll.isAncestorOf(dialog.buttons)
    finally:
        dialog.close()
