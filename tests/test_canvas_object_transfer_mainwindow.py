from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace
from typing import Any, cast

from PySide6.QtGui import QAction
from PySide6.QtWidgets import QDialog, QMenu, QWidget

from geoworkbench.domain.models import CanvasObject, Project, Well
from geoworkbench.project.canvas_object_transfer_coordinator import (
    CanvasObjectTransferCoordinator,
)
from geoworkbench.project.session import ProjectSession
from geoworkbench.services.localization import AppLanguage
from geoworkbench.ui import main_window_drilling


class _StatusBar:
    def __init__(self) -> None:
        self.messages: list[str] = []

    def showMessage(self, message: str) -> None:
        self.messages.append(message)


class _WindowProbe:
    def __init__(self, session: ProjectSession) -> None:
        self.session = session
        self.project_path = Path("project.geologpkg")
        self.project_controller = object()
        self.canvas_object_transfer_coordinator = CanvasObjectTransferCoordinator(
            self.session,
            cast(Any, self.project_controller),
        )
        self.language = AppLanguage.EN
        self.status = _StatusBar()
        self.background_save_acknowledged = 0
        self.canvas_refreshes: list[str] = []

    def _canvas_object_transfer_text(self, ru: str, kk: str, en: str) -> str:
        return {AppLanguage.RU: ru, AppLanguage.KK: kk, AppLanguage.EN: en}[
            self.language
        ]

    def statusBar(self) -> _StatusBar:
        return self.status

    def _acknowledge_background_project_save(self) -> None:
        self.background_save_acknowledged += 1

    def _refresh_transferred_canvas_layer(self, target_well_id: str) -> None:
        self.canvas_refreshes.append(target_well_id)


class _TabletProbe:
    def __init__(self) -> None:
        self.image_assets: dict[str, object] | None = None
        self.canvas_objects: list[CanvasObject] | None = None

    def set_image_assets(self, assets: dict[str, object]) -> None:
        self.image_assets = assets

    def set_canvas_objects(self, objects: list[CanvasObject]) -> None:
        self.canvas_objects = objects


def _session() -> ProjectSession:
    source = Well("source", "Source")
    target = Well("target", "Target")
    return ProjectSession(
        project=Project(
            "project",
            "Project",
            wells={source.well_id: source, target.well_id: target},
        ),
        current_well_id=target.well_id,
    )


def test_main_window_canvas_transfer_acknowledges_save_and_refreshes_only_annotations(
    monkeypatch,
) -> None:
    probe = _WindowProbe(_session())
    captured: dict[str, object] = {}

    class _Dialog:
        def __init__(self, application, target_well_id, *, language, parent) -> None:
            captured["application"] = application
            captured["target_well_id"] = target_well_id
            captured["language"] = language
            captured["parent"] = parent
            self.outcome = SimpleNamespace(
                copied_object_ids=("drawing-a", "drawing-b")
            )

        def exec(self) -> QDialog.DialogCode:
            return QDialog.DialogCode.Accepted

    monkeypatch.setattr(main_window_drilling, "CanvasObjectTransferDialog", _Dialog)

    main_window_drilling.MainWindow.show_canvas_object_transfer(probe)

    assert isinstance(captured["application"], CanvasObjectTransferCoordinator)
    assert captured["application"] is probe.canvas_object_transfer_coordinator
    assert captured["target_well_id"] == "target"
    assert captured["language"] is AppLanguage.EN
    assert captured["parent"] is probe
    assert probe.background_save_acknowledged == 1
    assert probe.canvas_refreshes == ["target"]
    assert probe.status.messages == ["Drawings transferred and saved: 2."]


def test_main_window_canvas_transfer_noop_does_not_acknowledge_or_refresh(
    monkeypatch,
) -> None:
    probe = _WindowProbe(_session())

    class _Dialog:
        def __init__(self, *_args, **_kwargs) -> None:
            self.outcome = SimpleNamespace(copied_object_ids=())

        def exec(self) -> QDialog.DialogCode:
            return QDialog.DialogCode.Accepted

    monkeypatch.setattr(main_window_drilling, "CanvasObjectTransferDialog", _Dialog)

    main_window_drilling.MainWindow.show_canvas_object_transfer(probe)

    assert probe.background_save_acknowledged == 0
    assert probe.canvas_refreshes == []
    assert probe.status.messages == ["Drawing transfer: no changes."]


def test_main_window_canvas_transfer_requires_saved_project(monkeypatch) -> None:
    probe = _WindowProbe(_session())
    probe.project_path = None
    messages: list[str] = []
    dialog_created = False

    class _Dialog:
        def __init__(self, *_args, **_kwargs) -> None:
            nonlocal dialog_created
            dialog_created = True

    monkeypatch.setattr(main_window_drilling, "CanvasObjectTransferDialog", _Dialog)
    monkeypatch.setattr(
        main_window_drilling.QMessageBox,
        "information",
        lambda _parent, _title, text: messages.append(text),
    )

    main_window_drilling.MainWindow.show_canvas_object_transfer(probe)

    assert dialog_created is False
    assert messages == [
        "Save the project first: a confirmed transfer must be persisted "
        "to the project file immediately."
    ]


def test_post_save_canvas_refresh_does_not_adopt_unscoped_annotations() -> None:
    drawing = CanvasObject(
        object_id="legacy-drawing",
        object_type="annotation",
        anchor_type="depth",
        x=0.1,
        y=1200.0,
        width=120.0,
        height=60.0,
        properties={"text": "legacy"},
    )
    target = Well("target", "Target", canvas_objects=[drawing])
    session = ProjectSession(
        project=Project("project", "Project", wells={target.well_id: target}),
        current_well_id=target.well_id,
        current_dataset_id="dataset",
        dirty=False,
    )
    tablet = _TabletProbe()
    probe = SimpleNamespace(session=session, tablet_view=tablet)

    main_window_drilling.MainWindow._refresh_transferred_canvas_layer(
        probe,
        target.well_id,
    )

    assert drawing.properties == {"text": "legacy"}
    assert session.dirty is False
    assert tablet.image_assets == {}
    assert tablet.canvas_objects == []


def test_canvas_transfer_action_is_inserted_before_open_data_and_localized(qapp) -> None:
    class _ActionHost(QWidget):
        def __init__(self) -> None:
            super().__init__()
            self.language = AppLanguage.RU
            self.file_menu = QMenu(self)
            self.open_data_action = QAction("Open", self)
            self.file_menu.addAction(self.open_data_action)

        def _menu_by_i18n_key(self, key: str) -> QMenu | None:
            return self.file_menu if key == "menu.file" else None

        def _canvas_object_transfer_text(self, ru: str, kk: str, en: str) -> str:
            return {AppLanguage.RU: ru, AppLanguage.KK: kk, AppLanguage.EN: en}[
                self.language
            ]

        def _retranslate_canvas_object_transfer_action(self) -> None:
            main_window_drilling.MainWindow._retranslate_canvas_object_transfer_action(
                self
            )

        def show_canvas_object_transfer(self) -> None:
            pass

    host = _ActionHost()
    main_window_drilling.MainWindow._install_canvas_object_transfer_action(host)

    actions = host.file_menu.actions()
    assert host.canvas_object_transfer_action.objectName() == "canvasObjectTransferAction"
    assert actions.index(host.canvas_object_transfer_action) < actions.index(
        host.open_data_action
    )
    assert host.canvas_object_transfer_action.text() == (
        "Перенести пользовательские рисунки из другой скважины…"
    )
    host.close()


def test_main_window_canvas_transfer_uses_session_bound_coordinator_source_contract() -> None:
    source = Path("src/geoworkbench/ui/main_window_drilling.py").read_text(encoding="utf-8")

    assert "CanvasObjectTransferCoordinator(" in source
    assert 'name="canvas_object_transfer"' in source
    assert "self.canvas_object_transfer_coordinator" in source
    assert "CanvasObjectTransferController(self.session)" not in source
    assert "CanvasObjectTransferWorkflow(" not in source
