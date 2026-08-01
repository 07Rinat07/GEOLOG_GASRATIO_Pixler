from __future__ import annotations

import os
from weakref import ReferenceType, ref

from PySide6.QtCore import QEasingCurve, QEvent, QObject, QPropertyAnimation
from PySide6.QtWidgets import (
    QApplication,
    QGraphicsOpacityEffect,
    QMainWindow,
    QPushButton,
    QToolButton,
    QWidget,
)

_ANIMATION_DISABLED_ENV = "GEOLOG_DISABLE_UI_ANIMATIONS"
_EFFECT_ATTRIBUTE = "_geolog_button_opacity_effect"
_ANIMATION_ATTRIBUTE = "_geolog_button_opacity_animation"
_TARGET_PROPERTY = "_geolog_button_opacity_target"


class ButtonAnimationController(QObject):
    """Provide a lightweight animated response for buttons in one main window.

    The controller is installed as an application event filter so buttons created
    later in dialogs and workspaces receive the same behaviour automatically.
    Only opacity is animated; widget geometry and layouts never change.
    """

    HOVER_OPACITY = 0.94
    PRESSED_OPACITY = 0.80
    HOVER_DURATION_MS = 120
    PRESS_DURATION_MS = 70
    RELEASE_DURATION_MS = 110
    LEAVE_DURATION_MS = 150

    def __init__(self, window: QMainWindow) -> None:
        super().__init__(window)
        self.window = window
        self.enabled = os.environ.get(_ANIMATION_DISABLED_ENV, "").strip() not in {
            "1",
            "true",
            "yes",
            "on",
        }
        application = QApplication.instance()
        self._application = application
        if application is not None and self.enabled:
            application.installEventFilter(self)

    def eventFilter(self, watched: QObject, event: QEvent) -> bool:  # noqa: N802
        if not self.enabled or not isinstance(watched, (QPushButton, QToolButton)):
            return False
        button = watched
        if not self._belongs_to_window(button):
            return False
        if bool(button.property("disableButtonAnimation")):
            self._restore_immediately(button)
            return False

        event_type = event.type()
        if event_type == QEvent.Type.Enter and button.isEnabled():
            self._animate(button, self.HOVER_OPACITY, self.HOVER_DURATION_MS)
        elif event_type == QEvent.Type.MouseButtonPress and button.isEnabled():
            self._animate(button, self.PRESSED_OPACITY, self.PRESS_DURATION_MS)
        elif event_type == QEvent.Type.MouseButtonRelease and button.isEnabled():
            target = self.HOVER_OPACITY if button.underMouse() else 1.0
            self._animate(button, target, self.RELEASE_DURATION_MS)
        elif event_type == QEvent.Type.Leave:
            self._animate(button, 1.0, self.LEAVE_DURATION_MS)
        elif event_type in {
            QEvent.Type.Hide,
            QEvent.Type.EnabledChange,
            QEvent.Type.Destroy,
        }:
            if event_type == QEvent.Type.Destroy or not button.isEnabled():
                self._restore_immediately(button)
        return False

    def _belongs_to_window(self, widget: QWidget) -> bool:
        current: QWidget | None = widget
        while current is not None:
            if current is self.window:
                return True
            current = current.parentWidget()
        return False

    def _animate(self, button: QWidget, target: float, duration_ms: int) -> None:
        effect = getattr(button, _EFFECT_ATTRIBUTE, None)
        animation = getattr(button, _ANIMATION_ATTRIBUTE, None)

        if not isinstance(effect, QGraphicsOpacityEffect):
            existing_effect = button.graphicsEffect()
            if existing_effect is not None:
                return
            effect = QGraphicsOpacityEffect(button)
            effect.setOpacity(1.0)
            button.setGraphicsEffect(effect)
            setattr(button, _EFFECT_ATTRIBUTE, effect)

        if not isinstance(animation, QPropertyAnimation):
            animation = QPropertyAnimation(effect, b"opacity", button)
            animation.setEasingCurve(QEasingCurve.Type.OutCubic)
            button_reference: ReferenceType[QWidget] = ref(button)
            animation.finished.connect(
                lambda reference=button_reference: self._animation_finished(reference)
            )
            setattr(button, _ANIMATION_ATTRIBUTE, animation)

        button.setProperty(_TARGET_PROPERTY, float(target))
        animation.stop()
        animation.setTargetObject(effect)
        animation.setDuration(max(1, int(duration_ms)))
        animation.setStartValue(float(effect.opacity()))
        animation.setEndValue(float(target))
        animation.start()

    def _animation_finished(self, button_reference: ReferenceType[QWidget]) -> None:
        button = button_reference()
        if button is None:
            return
        target = button.property(_TARGET_PROPERTY)
        try:
            target_value = float(target)
        except (TypeError, ValueError):
            target_value = 1.0
        if target_value >= 0.999 and not button.underMouse():
            self._detach_effect(button)

    def _restore_immediately(self, button: QWidget) -> None:
        effect = getattr(button, _EFFECT_ATTRIBUTE, None)
        if isinstance(effect, QGraphicsOpacityEffect):
            effect.setOpacity(1.0)
        self._detach_effect(button)

    @staticmethod
    def _detach_effect(button: QWidget) -> None:
        animation = getattr(button, _ANIMATION_ATTRIBUTE, None)
        if isinstance(animation, QPropertyAnimation):
            animation.stop()
            animation.setTargetObject(None)  # type: ignore[arg-type]

        effect = getattr(button, _EFFECT_ATTRIBUTE, None)
        if isinstance(effect, QGraphicsOpacityEffect) and button.graphicsEffect() is effect:
            button.setGraphicsEffect(None)  # type: ignore[arg-type]

        for attribute in (_ANIMATION_ATTRIBUTE, _EFFECT_ATTRIBUTE):
            try:
                delattr(button, attribute)
            except AttributeError:
                pass
        button.setProperty(_TARGET_PROPERTY, None)


def install_button_animations(window: QMainWindow) -> ButtonAnimationController:
    """Install or return the shared animation controller for ``window``."""

    existing = getattr(window, "_button_animation_controller", None)
    if isinstance(existing, ButtonAnimationController):
        return existing
    controller = ButtonAnimationController(window)
    setattr(window, "_button_animation_controller", controller)
    return controller
