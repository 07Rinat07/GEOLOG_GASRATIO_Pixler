from PySide6.QtWidgets import QCheckBox, QComboBox, QDoubleSpinBox, QLabel, QWidget
from geoworkbench.ui.file_workspace_runtime import FileWorkspaceWidget as _RuntimeWorkspace

class FileWorkspaceWidget(_RuntimeWorkspace):
    depth_ground_elevation: QDoubleSpinBox
    depth_reference_kind: QComboBox
    depth_datum_height: QDoubleSpinBox
    depth_measured_depth: QDoubleSpinBox
    depth_vertical_well: QCheckBox
    depth_true_vertical_depth: QDoubleSpinBox
    depth_result: QLabel
    def __init__(self, parent: QWidget | None = ..., *, language: str = ...) -> None: ...
