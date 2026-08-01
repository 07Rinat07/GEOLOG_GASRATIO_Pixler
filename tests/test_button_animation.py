from __future__ import annotations

import pytest
from PySide6.QtCore import QEvent
from PySide6.QtTest import QTest
from PySide6.QtWidgets import (
    QApplication,
    QGraphicsOpacityEffect,
    QPushButton,
    QToolButton,
)

from geoworkbench.services.localization import AppLanguage
from geoworkbench.ui.button_animation import ButtonAnimationController
from geoworkbench.ui.main_window import MainWindow


def _finish_deferred_setup(qapp) -> None:
    for _ in range(4):
        qapp.processEvents()


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
        QTest.qWait(controller.HOVER_DURATION_MS + 40)
        assert effect.opacity() == pytest.approx(controller.HOVER_OPACITY, abs=0.03)

        QApplication.sendEvent(button, QEvent(QEvent.Type.Leave))
        QTest.qWait(controller.LEAVE_DURATION_MS + 60)
        assert button.graphicsEffect() is None

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
    QTest.qWait(controller.HOVER_DURATION_MS + 30)
    hover_effect = button.graphicsEffect()
    assert isinstance(hover_effect, QGraphicsOpacityEffect)
    hover_opacity = hover_effect.opacity()

    controller.eventFilter(button, QEvent(QEvent.Type.MouseButtonPress))
    QTest.qWait(controller.PRESS_DURATION_MS + 30)
    pressed_effect = button.graphicsEffect()
    assert isinstance(pressed_effect, QGraphicsOpacityEffect)
    assert pressed_effect.opacity() < hover_opacity
    assert pressed_effect.opacity() == pytest.approx(controller.PRESSED_OPACITY, abs=0.03)
    assert button.geometry() == original_geometry

    controller.eventFilter(button, QEvent(QEvent.Type.Leave))
    QTest.qWait(controller.LEAVE_DURATION_MS + 60)
    assert button.graphicsEffect() is None
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
