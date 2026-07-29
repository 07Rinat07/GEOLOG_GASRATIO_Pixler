from __future__ import annotations

from PySide6.QtWidgets import (
    QDoubleSpinBox,
    QLineEdit,
    QSpinBox,
    QToolButton,
    QWidget,
)

from geoworkbench.files.enhanced_document_service import EnhancedDocumentService
from geoworkbench.ui.file_workspace_expert import FileWorkspaceWidget as _ExpertFileWorkspaceWidget


class FileWorkspaceWidget(_ExpertFileWorkspaceWidget):
    language: str
    document_service: EnhancedDocumentService
    eraser_button: QToolButton
    eraser_size: QSpinBox
    text_button: QToolButton
    replace_text_button: QToolButton
    expression_input: QLineEdit
    expression_result: QLineEdit
    converter_value: QLineEdit
    converter_result: QLineEdit
    pipe_wall_mm: QDoubleSpinBox
    pipe_length_m: QDoubleSpinBox
    pipe_density: QDoubleSpinBox

    def __init__(
        self,
        parent: QWidget | None = ...,
        *,
        language: str = ...,
    ) -> None: ...

    def _t(self, key: str, **values: object) -> str: ...
    def show_section(self, index: int) -> None: ...
