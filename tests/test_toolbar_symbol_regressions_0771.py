from __future__ import annotations

from pathlib import Path

from geoworkbench.project.annotation_schema import (
    AnnotationAnchor,
    AnnotationKind,
    AnnotationRecord,
)
from geoworkbench.tablet.annotation_interaction import (
    CATALOG_SYMBOL_MINIMUM_DIMENSION,
    resize_annotation_geometry,
)
from geoworkbench.tablet.annotation_layout import annotation_box_rect


ROOT = Path(__file__).resolve().parents[1]


def _record(
    kind: AnnotationKind,
    *,
    width: float,
    height: float,
    symbol_id: str | None = None,
) -> AnnotationRecord:
    return AnnotationRecord(
        annotation_id="a1",
        kind=kind,
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
        symbol_id=symbol_id,
    )


def test_catalog_symbol_layout_does_not_restore_generic_40_by_24_minimum() -> None:
    box = annotation_box_rect(
        _record(AnnotationKind.SYMBOL, width=1.0, height=7.0, symbol_id="bit")
    )

    assert box.width == 1.0
    assert box.height == 7.0


def test_normal_annotation_layout_keeps_safe_minimum() -> None:
    box = annotation_box_rect(
        _record(AnnotationKind.COMMENT, width=1.0, height=1.0)
    )

    assert box.width == 40.0
    assert box.height == 24.0


def test_catalog_symbol_can_be_narrowed_to_one_logical_pixel() -> None:
    assert CATALOG_SYMBOL_MINIMUM_DIMENSION == 1.0
    geometry = resize_annotation_geometry(
        10,
        20,
        100,
        60,
        "e",
        -500,
        0,
        minimum_width=CATALOG_SYMBOL_MINIMUM_DIMENSION,
        minimum_height=CATALOG_SYMBOL_MINIMUM_DIMENSION,
    )
    assert geometry == (10, 20, 1.0, 60)


def test_top_toolbars_have_hard_window_cap_and_zero_minimum_hint() -> None:
    source = (ROOT / "src/geoworkbench/ui/main_window.py").read_text(encoding="utf-8")

    assert "class _ConstrainedToolBar(QToolBar)" in source
    assert "def _cap_toolbar_rows_to_window" in source
    assert "self.main_toolbar_row.setFixedWidth(main_cap)" in source
    assert "self.form_edit_row.setFixedWidth(form_cap)" in source
    assert "self.form_edit_toolbar.visibilityChanged.connect" in source
    assert "action.changed.connect(self._schedule_toolbar_adaptation)" in source
    assert "self._schedule_toolbar_adaptation()" in source[
        source.index("def _set_tablet_edit_mode") : source.index(
            "def save_current_tablet_as_user_form"
        )
    ]
