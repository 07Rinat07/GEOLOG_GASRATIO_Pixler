from __future__ import annotations

from dataclasses import dataclass

from PySide6.QtCore import QEvent, QObject, QSize, Qt
from PySide6.QtGui import QAction
from PySide6.QtWidgets import (
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QScrollArea,
    QSizePolicy,
    QToolButton,
    QVBoxLayout,
    QWidget,
)

from geoworkbench.services.localization import AppLanguage, Localizer
from geoworkbench.ui.branding import logo_pixmap
from geoworkbench.ui.drilling_animation import DrillingAnimation


@dataclass(frozen=True, slots=True)
class HomeAction:
    action: QAction
    description_key: str
    object_name: str
    primary: bool = False


class _ActionCard(QFrame):
    def __init__(self, spec: HomeAction, localizer: Localizer, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.spec = spec
        self.setObjectName("homeActionCard")
        self.setProperty("primary", spec.primary)
        self.setMinimumHeight(132)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(18, 16, 18, 15)
        layout.setSpacing(8)

        self.button = QToolButton(self)
        self.button.setObjectName(spec.object_name)
        self.button.setDefaultAction(spec.action)
        self.button.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextBesideIcon)
        self.button.setIconSize(QSize(26, 26))
        self.button.setAutoRaise(False)
        self.button.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        layout.addWidget(self.button)

        self.description = QLabel(self)
        self.description.setObjectName("homeActionDescription")
        self.description.setWordWrap(True)
        self.description.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignTop)
        layout.addWidget(self.description, 1)
        self.retranslate(localizer)

    def retranslate(self, localizer: Localizer) -> None:
        self.description.setText(localizer.text(self.spec.description_key))


class HomePage(QWidget):
    """A clear, scrollable starting point for the desktop workflow."""

    def __init__(
        self,
        actions: tuple[HomeAction, ...],
        workspace_action: QAction,
        *,
        language: AppLanguage,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.setObjectName("homePage")
        self.language = language
        self.localizer = Localizer.create(language)
        self._dataset_name: str | None = None
        self._cards: list[_ActionCard] = []

        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        self.scroll = QScrollArea(self)
        self.scroll.setObjectName("homeScrollArea")
        self.scroll.setWidgetResizable(True)
        self.scroll.setFrameShape(QFrame.Shape.NoFrame)
        self.scroll.viewport().installEventFilter(self)
        outer.addWidget(self.scroll)

        self.content = QWidget(self.scroll)
        self.content.setObjectName("homeContent")
        content_layout = QVBoxLayout(self.content)
        content_layout.setContentsMargins(34, 28, 34, 34)
        content_layout.setSpacing(22)
        self.scroll.setWidget(self.content)
        self.scroll.setAlignment(Qt.AlignmentFlag.AlignHCenter | Qt.AlignmentFlag.AlignTop)
        content = self.content

        header = QHBoxLayout()
        header.setSpacing(18)
        logo = QLabel(content)
        logo.setPixmap(logo_pixmap(72))
        logo.setFixedSize(76, 76)
        logo.setAlignment(Qt.AlignmentFlag.AlignCenter)
        header.addWidget(logo, 0, Qt.AlignmentFlag.AlignTop)
        heading = QVBoxLayout()
        heading.setSpacing(4)
        self.eyebrow = QLabel(content)
        self.eyebrow.setObjectName("homeEyebrow")
        self.title = QLabel(content)
        self.title.setObjectName("homeTitle")
        self.subtitle = QLabel(content)
        self.subtitle.setObjectName("homeSubtitle")
        self.subtitle.setWordWrap(True)
        heading.addWidget(self.eyebrow)
        heading.addWidget(self.title)
        heading.addWidget(self.subtitle)
        header.addLayout(heading, 1)
        self.drilling_animation = DrillingAnimation(dark=False, parent=content)
        self.drilling_animation.setObjectName("homeDrillingAnimation")
        self.drilling_animation.setFixedSize(250, 124)
        header.addWidget(self.drilling_animation, 0, Qt.AlignmentFlag.AlignRight)
        content_layout.addLayout(header)

        workspace = QFrame(content)
        workspace.setObjectName("homeWorkspaceCard")
        workspace_layout = QHBoxLayout(workspace)
        workspace_layout.setContentsMargins(18, 14, 14, 14)
        workspace_layout.setSpacing(16)
        workspace_text = QVBoxLayout()
        workspace_text.setSpacing(3)
        self.workspace_caption = QLabel(workspace)
        self.workspace_caption.setObjectName("homeWorkspaceCaption")
        self.workspace_value = QLabel(workspace)
        self.workspace_value.setObjectName("homeWorkspaceValue")
        self.workspace_value.setWordWrap(True)
        workspace_text.addWidget(self.workspace_caption)
        workspace_text.addWidget(self.workspace_value)
        workspace_layout.addLayout(workspace_text, 1)
        self.workspace_button = QToolButton(workspace)
        self.workspace_button.setObjectName("homeWorkspaceButton")
        self.workspace_button.setDefaultAction(workspace_action)
        self.workspace_button.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextBesideIcon)
        self.workspace_button.setIconSize(QSize(22, 22))
        self.workspace_button.setAutoRaise(False)
        workspace_layout.addWidget(self.workspace_button)
        content_layout.addWidget(workspace)

        self.quick_title = QLabel(content)
        self.quick_title.setObjectName("homeSectionTitle")
        content_layout.addWidget(self.quick_title)
        cards = QGridLayout()
        cards.setHorizontalSpacing(14)
        cards.setVerticalSpacing(14)
        cards.setColumnStretch(0, 1)
        cards.setColumnStretch(1, 1)
        for index, spec in enumerate(actions):
            card = _ActionCard(spec, self.localizer, content)
            cards.addWidget(card, index // 2, index % 2)
            self._cards.append(card)
        content_layout.addLayout(cards)

        self.workflow_title = QLabel(content)
        self.workflow_title.setObjectName("homeSectionTitle")
        content_layout.addWidget(self.workflow_title)
        steps = QHBoxLayout()
        steps.setSpacing(12)
        self._step_titles: list[QLabel] = []
        self._step_descriptions: list[QLabel] = []
        for number in range(1, 4):
            step = QFrame(content)
            step.setObjectName("homeStep")
            step_layout = QVBoxLayout(step)
            step_layout.setContentsMargins(16, 14, 16, 14)
            step_layout.setSpacing(5)
            badge = QLabel(str(number), step)
            badge.setObjectName("homeStepNumber")
            badge.setAlignment(Qt.AlignmentFlag.AlignCenter)
            badge.setFixedSize(28, 28)
            title = QLabel(step)
            title.setObjectName("homeStepTitle")
            description = QLabel(step)
            description.setObjectName("homeStepDescription")
            description.setWordWrap(True)
            step_layout.addWidget(badge)
            step_layout.addWidget(title)
            step_layout.addWidget(description, 1)
            steps.addWidget(step, 1)
            self._step_titles.append(title)
            self._step_descriptions.append(description)
        content_layout.addLayout(steps)
        content_layout.addStretch(1)

        self.setStyleSheet(
            "QWidget#homePage, QWidget#homeContent { background: #f4f7fb; }"
            "QScrollArea#homeScrollArea { background: #f4f7fb; }"
            "QLabel#homeEyebrow { color: #2563eb; font-size: 11px; font-weight: 800; "
            "letter-spacing: 1px; }"
            "QLabel#homeTitle { color: #0f172a; font-size: 28px; font-weight: 800; }"
            "QLabel#homeSubtitle { color: #475569; font-size: 13px; }"
            "QFrame#homeWorkspaceCard { background: #eaf2ff; border: 1px solid #bfdbfe; "
            "border-radius: 10px; }"
            "QLabel#homeWorkspaceCaption { color: #1d4ed8; font-weight: 700; }"
            "QLabel#homeWorkspaceValue { color: #334155; }"
            "QLabel#homeSectionTitle { color: #0f172a; font-size: 17px; font-weight: 750; "
            "margin-top: 2px; }"
            "QFrame#homeActionCard, QFrame#homeStep { background: white; border: 1px solid #dbe3ee; "
            "border-radius: 10px; }"
            "QFrame#homeActionCard[primary=\"true\"] { border: 1px solid #93c5fd; "
            "background: #f8fbff; }"
            "QToolButton { background: #ffffff; border: 1px solid #cbd5e1; border-radius: 7px; "
            "color: #0f172a; font-weight: 700; min-height: 34px; padding: 5px 11px; "
            "text-align: left; }"
            "QToolButton:hover { background: #eff6ff; border-color: #60a5fa; }"
            "QToolButton:pressed { background: #dbeafe; }"
            "QToolButton:disabled { color: #94a3b8; background: #f8fafc; }"
            "QLabel#homeActionDescription, QLabel#homeStepDescription { color: #64748b; }"
            "QLabel#homeStepNumber { color: white; background: #2563eb; border-radius: 14px; "
            "font-weight: 800; }"
            "QLabel#homeStepTitle { color: #1e293b; font-weight: 750; }"
        )
        self.retranslate(language)

    def eventFilter(self, watched: QObject, event: QEvent) -> bool:  # noqa: N802
        if watched is self.scroll.viewport() and event.type() is QEvent.Type.Resize:
            viewport_width = self.scroll.viewport().width()
            if viewport_width > 0:
                self.content.setFixedWidth(min(1120, viewport_width))
                self.drilling_animation.setVisible(viewport_width >= 820)
        return super().eventFilter(watched, event)

    def set_workspace_dataset(self, dataset_name: str | None) -> None:
        self._dataset_name = dataset_name
        self._update_workspace_text()

    def retranslate(self, language: AppLanguage) -> None:
        self.language = language
        self.localizer = Localizer.create(language)
        self.eyebrow.setText(self.localizer.text("home.eyebrow"))
        self.title.setText(self.localizer.text("home.title"))
        self.subtitle.setText(self.localizer.text("home.subtitle"))
        self.workspace_caption.setText(self.localizer.text("home.workspace_caption"))
        self.quick_title.setText(self.localizer.text("home.quick_actions"))
        self.workflow_title.setText(self.localizer.text("home.workflow"))
        for card in self._cards:
            card.retranslate(self.localizer)
        for index, (title, description) in enumerate(
            zip(self._step_titles, self._step_descriptions, strict=True), start=1
        ):
            title.setText(self.localizer.text(f"home.step{index}.title"))
            description.setText(self.localizer.text(f"home.step{index}.description"))
        self._update_workspace_text()

    def _update_workspace_text(self) -> None:
        if self._dataset_name:
            self.workspace_value.setText(
                self.localizer.text("home.workspace_ready", dataset=self._dataset_name)
            )
        else:
            self.workspace_value.setText(self.localizer.text("home.workspace_empty"))
