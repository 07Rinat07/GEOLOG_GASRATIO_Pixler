from pathlib import Path


def test_annotation_confirmation_uses_value_comparison() -> None:
    source = Path("src/geoworkbench/ui/main_window.py").read_text(encoding="utf-8")
    start = source.index("def _delete_annotation_from_tablet")
    end = source.index("def _duplicate_annotation_from_tablet", start)
    block = source[start:end]
    assert "answer != QMessageBox.StandardButton.Yes" in block
    assert "answer is not QMessageBox.StandardButton.Yes" not in block


def test_annotation_dialog_notifies_main_window_after_crud() -> None:
    source = Path("src/geoworkbench/ui/depth_annotations_dialog.py").read_text(encoding="utf-8")
    assert "annotations_changed = Signal()" in source
    assert "self.annotations_changed.emit()" in source


def test_main_window_filters_annotation_layer_by_current_form() -> None:
    source = Path("src/geoworkbench/ui/main_window.py").read_text(encoding="utf-8")
    assert "canvas_objects_for_current_scope()" in source
    assert "adopt_unscoped_annotations()" in source


def test_single_item_editor_exposes_delete_action() -> None:
    source = Path("src/geoworkbench/ui/depth_annotations_dialog.py").read_text(encoding="utf-8")
    assert 'setObjectName("annotation-delete-single-button")' in source
    assert "def _delete_single_item" in source
    assert "answer != QMessageBox.StandardButton.Yes" in source


def test_project_open_waits_for_layout_before_loading_scoped_annotations() -> None:
    source = Path("src/geoworkbench/ui/main_window.py").read_text(encoding="utf-8")
    start = source.index("def _show_current_dataset")
    end = source.index("def show_las_editor", start)
    block = source[start:end]
    assert "self.tablet_view.set_canvas_objects([])" in block
    assert "self._refresh_annotation_layer()" in block
    assert "set_canvas_objects(well.canvas_objects" not in block


def test_masterlog_print_filters_annotations_by_active_form_scope() -> None:
    source = Path("src/geoworkbench/printing/masterlog_renderer.py").read_text(encoding="utf-8")
    assert "annotation_scope_id_for_session(session)" in source
    assert "annotation_matches_scope(record, active_scope_id)" in source


def test_legacy_scope_migration_marks_open_project_dirty_for_saving() -> None:
    source = Path("src/geoworkbench/ui/main_window.py").read_text(encoding="utf-8")
    assert "annotation_scope_migration_required" in source
    assert "self.session.dirty = annotation_scope_migration_required" in source


def test_annotation_context_menu_compares_qactions_by_value() -> None:
    source = Path("src/geoworkbench/tablet/tablet_view.py").read_text(encoding="utf-8")
    start = source.index("def _show_annotation_context_menu")
    end = source.index("def _curve_geometry_key", start)
    block = source[start:end]
    assert "chosen == delete_action" in block
    assert "chosen is delete_action" not in block


def test_controller_blocks_stale_cross_form_edit_and_delete_ids() -> None:
    source = Path("src/geoworkbench/project/annotation_controller.py").read_text(
        encoding="utf-8"
    )
    assert "def _require_current_item" in source
    assert "Аннотация не принадлежит текущей форме" in source
    remove_start = source.index("def remove(")
    remove_end = source.index("def install_image", remove_start)
    assert "self._require_current_item(annotation_id)" in source[remove_start:remove_end]
