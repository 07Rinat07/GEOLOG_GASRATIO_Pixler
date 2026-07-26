from __future__ import annotations

from pathlib import Path

import pytest

from geoworkbench.project.annotation_schema import (
    CATALOG_SYMBOL_MINIMUM_DIMENSION,
    AnnotationAnchor,
    AnnotationKind,
    AnnotationRecord,
    annotation_from_canvas,
    annotation_properties,
)
from geoworkbench.domain.models import CanvasObject
from geoworkbench.tablet.annotation_interaction import resize_annotation_geometry
from geoworkbench.tablet.annotation_layout import annotation_box_rect


ROOT = Path(__file__).resolve().parents[1]


def _symbol(width: float, height: float) -> AnnotationRecord:
    return AnnotationRecord(
        annotation_id="symbol-1",
        kind=AnnotationKind.SYMBOL,
        anchor=AnnotationAnchor.DEPTH,
        text="",
        track_id="gas",
        depth=100.0,
        axis_value=None,
        axis_id=None,
        parameter_mnemonic=None,
        parameter_value=None,
        unit="",
        x_fraction=0.5,
        offset_x=0.0,
        offset_y=0.0,
        width=width,
        height=height,
        symbol_id="catalog-bit",
    )


def test_symbol_has_only_subpixel_reference_floor() -> None:
    assert CATALOG_SYMBOL_MINIMUM_DIMENSION == 0.01
    box = annotation_box_rect(_symbol(0.01, 80.0))
    assert box.width == 0.01
    assert box.height == 80.0


def test_symbol_can_be_flattened_independently_from_east_or_north() -> None:
    horizontal = resize_annotation_geometry(
        10.0, 20.0, 100.0, 80.0, "e", -500.0, 0.0,
        minimum_width=CATALOG_SYMBOL_MINIMUM_DIMENSION,
        minimum_height=CATALOG_SYMBOL_MINIMUM_DIMENSION,
    )
    vertical = resize_annotation_geometry(
        10.0, 20.0, 100.0, 80.0, "n", 0.0, 500.0,
        minimum_width=CATALOG_SYMBOL_MINIMUM_DIMENSION,
        minimum_height=CATALOG_SYMBOL_MINIMUM_DIMENSION,
    )
    assert horizontal[:2] == (10.0, 20.0)
    assert horizontal[2] == pytest.approx(0.01)
    assert horizontal[3] == 80.0
    assert vertical[0] == 10.0
    assert vertical[1] == pytest.approx(99.99)
    assert vertical[2] == 100.0
    assert vertical[3] == pytest.approx(0.01)


def test_subpixel_symbol_geometry_survives_canvas_round_trip() -> None:
    source = _symbol(0.01, 52.5)
    canvas = CanvasObject(
        object_id=source.annotation_id,
        object_type="annotation",
        anchor_type=source.anchor.value,
        x=source.x_fraction,
        y=source.depth or 0.0,
        width=source.width,
        height=source.height,
        track_id=source.track_id,
        properties=annotation_properties(
            kind=source.kind,
            text=source.text,
            axis_value=source.axis_value,
            axis_id=source.axis_id,
            parameter_value=source.parameter_value,
            unit=source.unit,
            offset_x=source.offset_x,
            offset_y=source.offset_y,
            style=source.style,
            asset_ref=source.asset_ref,
            visible=source.visible,
            locked=source.locked,
            print_enabled=source.print_enabled,
            scope_id=source.scope_id,
            symbol_id=source.symbol_id,
            transparent_background=source.transparent_background,
        ),
    )
    restored = annotation_from_canvas(canvas)
    assert restored.width == 0.01
    assert restored.height == 52.5
    assert restored.kind is AnnotationKind.SYMBOL


def test_top_command_rows_are_not_docked_native_toolbars() -> None:
    source = (ROOT / "src/geoworkbench/ui/main_window.py").read_text(encoding="utf-8")
    create = source[source.index("def _create_toolbar"):source.index("def toggle_cursor_line")]
    assert "class _ResponsiveCommandBar(QFrame)" in source
    assert "This widget deliberately does not inherit ``QToolBar``" in source
    assert "class _ResponsiveToolbarHost" in source
    assert "self.toolbar_host_layout.addWidget(self.main_toolbar)" in create
    assert "self.toolbar_host_layout.addWidget(self.form_edit_toolbar)" in create
    assert "self.workspace_shell_layout.addWidget(self.toolbar_host)" in create
    assert "self.addToolBar(" not in create
    assert "self.addToolBarBreak(" not in create
    assert "self.main_toolbar = _ResponsiveCommandBar" in create
    assert "self.form_edit_toolbar = _ResponsiveCommandBar" in create
    assert "self.main_toolbar.addWidget" not in create
    assert "self.form_edit_toolbar.addWidget" not in create
    assert "def minimumSizeHint(self) -> QSize" in source
    assert "self.setMinimumSize(640, 480)" in source


def test_tiny_symbol_keeps_a_separate_usable_selection_frame() -> None:
    source = (ROOT / "src/geoworkbench/tablet/annotation_graphics.py").read_text(
        encoding="utf-8"
    )
    assert "def selection_rect(self) -> QRectF" in source
    assert "minimum_extent = 18.0" in source
    assert "rect = self.selection_rect()" in source
    assert "helper.selection_rect().contains(box_local)" in source
