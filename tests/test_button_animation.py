from __future__ import annotations

import pytest
from PySide6.QtCore import QEvent
from PySide6.QtTest import QTest
from PySide6.QtWidgets import (
    QApplication,
    QGraphicsOpacityEffect,
    QPushButton,
    QToolButton,
    QWidget,
)

from geoworkbench.services.localization import AppLanguage
from geoworkbench.ui.button_animation import ButtonAnimationController
from geoworkbench.ui.main_window import MainWindow


def _finish_deferred_setup(qapp) -> None:
    for _ in range(4):
        qapp.processEvents()


def _wait_for_opacity(
    effect: QGraphicsOpacityEffect,
    target: float,
    *,
    tolerance: float = 0.03,
    timeout_ms: int = 1_000,
) -> None:
    """Wait on the Qt event loop instead of assuming a loaded runner meets wall timing."""

    attempts = max(1, timeout_ms // 10)
    for _ in range(attempts):
        QApplication.processEvents()
        if abs(float(effect.opacity()) - target) <= tolerance:
            return
        QTest.qWait(10)
    assert effect.opacity() == pytest.approx(target, abs=tolerance)


def _wait_for_effect_detached(button: QWidget, *, timeout_ms: int = 1_000) -> None:
    attempts = max(1, timeout_ms // 10)
    for _ in range(attempts):
        QApplication.processEvents()
        if button.graphicsEffect() is None:
            return
        QTest.qWait(10)
    assert button.graphicsEffect() is None


def test_shared_controller_animates_buttons_created_after_startup(qapp) -> None:
    window = MainWindow(language=AppLanguage.RU)
    window.show()
    _finish_deferred_setup(qapp)

    controller = window._button_animation_controller
    assert isinstance(controller, ButtonAnimationController)

    push_button = QPushButton("Проверка", window)
    push_button.resize(140, 36)
    push_button.show()
    tool_button = QToolButton(window)
    tool_button.setText("Инструмент")
    tool_button.resize(140, 36)
    tool_button.move(0, 42)
    tool_button.show()
    qapp.processEvents()

    for button in (push_button, tool_button):
        QApplication.sendEvent(button, QEvent(QEvent.Type.Enter))
        qapp.processEvents()
        effect = button.graphicsEffect()
        assert isinstance(effect, QGraphicsOpacityEffect)
        _wait_for_opacity(effect, controller.HOVER_OPACITY)

        QApplication.sendEvent(button, QEvent(QEvent.Type.Leave))
        _wait_for_effect_detached(button)

    window.close()


def test_press_animation_is_stronger_than_hover_without_geometry_changes(qapp) -> None:
    window = MainWindow(language=AppLanguage.RU)
    window.show()
    _finish_deferred_setup(qapp)
    controller = window._button_animation_controller

    button = QPushButton("Нажать", window)
    button.setGeometry(10, 10, 160, 38)
    button.show()
    qapp.processEvents()
    original_geometry = button.geometry()

    controller.eventFilter(button, QEvent(QEvent.Type.Enter))
    hover_effect = button.graphicsEffect()
    assert isinstance(hover_effect, QGraphicsOpacityEffect)
    _wait_for_opacity(hover_effect, controller.HOVER_OPACITY)
    hover_opacity = hover_effect.opacity()

    controller.eventFilter(button, QEvent(QEvent.Type.MouseButtonPress))
    pressed_effect = button.graphicsEffect()
    assert isinstance(pressed_effect, QGraphicsOpacityEffect)
    _wait_for_opacity(pressed_effect, controller.PRESSED_OPACITY)
    assert pressed_effect.opacity() < hover_opacity
    assert pressed_effect.opacity() == pytest.approx(controller.PRESSED_OPACITY, abs=0.03)
    assert button.geometry() == original_geometry

    controller.eventFilter(button, QEvent(QEvent.Type.Leave))
    _wait_for_effect_detached(button)
    assert button.geometry() == original_geometry
    window.close()


def test_disabled_or_opted_out_buttons_are_not_animated(qapp) -> None:
    window = MainWindow(language=AppLanguage.RU)
    window.show()
    _finish_deferred_setup(qapp)

    disabled_button = QPushButton("Недоступно", window)
    disabled_button.setEnabled(False)
    disabled_button.show()
    QApplication.sendEvent(disabled_button, QEvent(QEvent.Type.Enter))
    qapp.processEvents()
    assert disabled_button.graphicsEffect() is None

    opted_out_button = QPushButton("Без анимации", window)
    opted_out_button.setProperty("disableButtonAnimation", True)
    opted_out_button.show()
    QApplication.sendEvent(opted_out_button, QEvent(QEvent.Type.Enter))
    qapp.processEvents()
    assert opted_out_button.graphicsEffect() is None

    window.close()
