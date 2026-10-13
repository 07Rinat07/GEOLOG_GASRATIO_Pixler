"""PLOT-FLAG-01: per-print VALUE selection never mutates persisted annotations."""

from dataclasses import replace

import pytest
from PySide6.QtCore import QPointF, QRectF, Qt
from PySide6.QtWidgets import QWidget

from geoworkbench.printing.print_job import PrintJobSettings, PrintOutputFormat
from geoworkbench.project.annotation_schema import AnnotationAnchor, AnnotationKind, AnnotationRecord
from geoworkbench.services.localization import AppLanguage
from geoworkbench.tablet.annotation_graphics import TabletAnnotationItem, TabletAnnotationOverlay
from geoworkbench.ui.print_center_dialog import PrintCenterDialog


def _record(
    annotation_id: str,
    *,
    kind: AnnotationKind = AnnotationKind.VALUE,
    print_enabled: bool = True,
) -> AnnotationRecord:
    return AnnotationRecord(
        annotation_id=annotation_id,
        kind=kind,
        anchor=AnnotationAnchor.DEPTH,
        text="Operator note",
        track_id="gas",
        depth=100.0,
        axis_value=100.0,
        axis_id="md",
        parameter_mnemonic="TG",
        parameter_value=15.5,
        unit="%",
        x_fraction=0.5,
        offset_x=18.0,
        offset_y=-36.0,
        width=200.0,
        height=76.0,
        visible=True,
        locked=False,
        print_enabled=print_enabled,
        scope_id="dataset:flags:default",
    )


def test_value_print_selection_hides_only_deselected_flags_and_restores_screen(qapp) -> None:
    first = _record("first")
    second = _record("second")
    comment = _record("comment", kind=AnnotationKind.COMMENT)
    disabled = _record("disabled", print_enabled=False)
    original = (first, second, comment, disabled)

    items = {record.annotation_id: TabletAnnotationItem(record) for record in original}
    assert all(item.isVisible() for item in items.values())
    for item in items.values():
        item.set_print_mode(True, included_value_ids=frozenset({"first"}))
    assert items["first"].isVisible()
    assert not items["second"].isVisible()
    assert items["comment"].isVisible()
    assert not items["disabled"].isVisible()

    for item in items.values():
        item.set_print_mode(False)
        assert item.isVisible()
        assert item.record == original[("first", "second", "comment", "disabled").index(item.annotation_id)]
    assert all(record.print_enabled == (record.annotation_id != "disabled") for record in original)


def test_value_filter_applies_to_overlay_sprites_without_editing_records(qapp) -> None:
    canvas = QWidget()
    canvas.resize(500, 400)
    overlay = TabletAnnotationOverlay(canvas)
    overlay.set_content_rect(QRectF(0, 0, 500, 400))
    records = [_record("a"), _record("b"), _record("note", kind=AnnotationKind.COMMENT)]
    overlay.set_entries([(record, QPointF(40.0, 80.0), None) for record in records])
    assert set(overlay.annotation_ids) == {"a", "b", "note"}

    overlay.set_print_mode(True, included_value_ids=frozenset({"a"}))
    assert overlay.annotation_item("a").isVisible()
    assert not overlay.annotation_item("b").isVisible()
    assert overlay.annotation_item("note").isVisible()
    assert not overlay._sprites["a"].isHidden()
    assert overlay._sprites["b"].isHidden()
    assert not overlay._sprites["note"].isHidden()

    overlay.set_print_mode(False)
    assert all(overlay.annotation_item(record.annotation_id).isVisible() for record in records)
    assert all(overlay.annotation_item(record.annotation_id).record == record for record in records)
    overlay.close()
    canvas.close()


@pytest.mark.parametrize("language", list(AppLanguage))
def test_print_center_selects_individual_value_flags_without_mutating_preferences(
    qapp, language: AppLanguage,
) -> None:
    dialog = PrintCenterDialog(
        language=language,
        printer_choices=(("Plotter", True),),
        value_flag_options=(("a", "TG: 15.5 % · 100 m"), ("b", "DT: 120 us/m · 101 m")),
    )
    try:
        assert not dialog.value_flags_group.isHidden()
        assert dialog.value_flags_tree.topLevelItemCount() == 2
        assert dialog.job_settings().included_value_annotation_ids == ("a", "b")
        dialog.value_flags_tree.topLevelItem(1).setCheckState(0, Qt.CheckState.Unchecked)
        assert dialog.job_settings().included_value_annotation_ids == ("a",)
        dialog.print_value_flags_check.setChecked(False)
        assert dialog.job_settings().included_value_annotation_ids == ()
        dialog.print_value_flags_check.setChecked(True)
        dialog.select_all_value_flags_button.click()
        assert dialog.job_settings().included_value_annotation_ids == ("a", "b")
        dialog.clear_value_flags_button.click()
        assert dialog.job_settings().included_value_annotation_ids == ()
        assert dialog.preferences().output_format is PrintOutputFormat.PRINTER
    finally:
        dialog.close()


def test_print_settings_reject_invalid_value_flag_ids_and_preserve_legacy_default() -> None:
    legacy = PrintJobSettings(output_format=PrintOutputFormat.PRINTER)
    assert legacy.included_value_annotation_ids is None
    assert replace(legacy, included_value_annotation_ids=()).included_value_annotation_ids == ()
    for ids in (("a", "a"), ("",), (" a", " a")):
        with pytest.raises(ValueError, match="флажков"):
            replace(legacy, included_value_annotation_ids=ids)
