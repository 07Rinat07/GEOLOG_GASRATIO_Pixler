import pytest
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QDialog, QFileDialog, QMessageBox

from geoworkbench.services.gis_gti_lithology_screening import ObservationQuality, RockFamily
from geoworkbench.services.localization import AppLanguage, Localizer
from geoworkbench.ui.lithology_mapping_dialog import LithologyMappingDialog
from test_report_geology_snapshot import _session
from test_main_window import bind_session


def _fill(dialog):
    dialog.source.setCurrentIndex(1)
    dialog.family.setCurrentIndex(dialog.family.findData(RockFamily.HALITE))
    dialog.quality.setCurrentIndex(dialog.quality.findData(ObservationQuality.VALIDATED))
    for key, value in dict(mapping_id="review-1", reviewer="Expert",
                           evidence="Synthetic acceptance only").items():
        dialog.fields[key].setText(value)


@pytest.mark.parametrize("language", list(AppLanguage))
def test_operator_reviews_explicit_family_without_mutating_source(qapp, language):
    session = _session()
    session.dirty = False
    before = repr(session.project)
    dialog = LithologyMappingDialog(session, language=language)
    assert dialog.source.currentData() is None
    assert dialog.family.currentData() is None and dialog.quality.currentData() is None
    assert all(not field.text() for field in dialog.fields.values())
    _fill(dialog)
    dialog.review.click()
    assert dialog.mapping.source.lithotype_id == "sandstone"
    assert dialog.mapping.rock_family is RockFamily.HALITE
    assert dialog.mapping.reviewer == "Expert"
    assert "review-1" in dialog.result_label.text()
    assert "lith-in" in dialog.source_label.text()
    assert dialog.source_label.textFormat() is Qt.TextFormat.PlainText
    assert dialog.result_label.textFormat() is Qt.TextFormat.PlainText
    assert repr(session.project) == before and not session.dirty
    dialog.reject()
    assert dialog.result() == QDialog.DialogCode.Rejected
    dialog.close()


@pytest.mark.parametrize("field", ["mapping_id", "reviewer", "evidence", "family", "quality", "source"])
def test_editing_inputs_clears_previous_result(qapp, field):
    dialog = LithologyMappingDialog(_session())
    _fill(dialog)
    dialog.review.click()
    assert dialog.mapping is not None
    if field in dialog.fields:
        dialog.fields[field].setText("Changed")
    else:
        getattr(dialog, field).setCurrentIndex(0)
    assert dialog.mapping is None and not dialog.result_label.text()
    dialog.close()


@pytest.mark.parametrize("change", ["source", "axis", "deleted", "unit", "description"])
def test_source_changes_require_reload_before_new_review(qapp, change):
    session = _session()
    dialog = LithologyMappingDialog(session)
    _fill(dialog)
    dialog.review.click()
    assert dialog.mapping is not None
    if change == "source":
        session.current_well.lithology[0].top_depth += 1
    elif change == "axis":
        session.current_dataset.active_index.values[1] += 0.5
    elif change == "deleted":
        session.current_well.lithology.clear()
    elif change == "unit":
        session.current_dataset.active_index.unit = "ft"
    else:
        session.current_well.lithology[0].description = "Changed"
    assert dialog.mapping is None
    assert dialog.result_label.text() == dialog._t("invalid")
    dialog.review.click()
    assert dialog.mapping is None
    if change in {"source", "axis", "description"}:
        dialog.reload.click()
        assert dialog.source.currentData() is None and dialog.mapping is None
        assert dialog.family.currentData() is None and dialog.quality.currentData() is None
        _fill(dialog)
        dialog.review.click()
        assert dialog.mapping is not None
    dialog.close()


@pytest.mark.parametrize("missing", ["source", "family", "quality", "evidence"])
def test_missing_choices_are_blocked_with_localized_message(qapp, missing):
    dialog = LithologyMappingDialog(_session())
    _fill(dialog)
    if missing in dialog.fields:
        dialog.fields[missing].clear()
    else:
        getattr(dialog, missing).setCurrentIndex(0)
    dialog.review.click()
    assert dialog.mapping is None
    assert dialog.result_label.text() == dialog._t(
        "invalid" if missing == "evidence" else "selection_required",
    )
    dialog.close()


@pytest.mark.parametrize("quality", list(ObservationQuality))
def test_operator_quality_is_preserved_without_defaults(qapp, quality):
    dialog = LithologyMappingDialog(_session())
    _fill(dialog)
    dialog.quality.setCurrentIndex(dialog.quality.findData(quality.value))
    dialog.review.click()
    assert dialog.mapping.quality is quality
    dialog.source.setCurrentIndex(2)
    assert dialog.family.currentData() is None and dialog.quality.currentData() is None
    assert dialog.mapping is None
    dialog.close()


def test_menu_opens_read_only_dialog_and_handles_absent_dataset(qapp, monkeypatch):
    from geoworkbench.ui.main_window import MainWindow

    window = MainWindow()
    session = _session()
    bind_session(window, session)
    session.dirty = False
    observed = []

    def run(dialog):
        assert dialog.session is session
        _fill(dialog)
        dialog.review.click()
        observed.append(dialog.mapping)
        return QDialog.DialogCode.Rejected

    monkeypatch.setattr(LithologyMappingDialog, "exec", run)
    for language in AppLanguage:
        window.change_language(language)
        assert window.lithology_mapping_action.text() == Localizer.create(language).text(
            "lithology_mapping.action",
        )
        window.lithology_mapping_action.trigger()
    assert len(observed) == 3 and all(item is not None for item in observed)
    assert not session.dirty
    messages = []
    monkeypatch.setattr(QMessageBox, "information", lambda *args: messages.append(args[2]))
    session.current_dataset_id = None
    window.lithology_mapping_action.trigger()
    assert messages == [window._t("lithology_mapping.select_dataset")]
    window.close()


@pytest.mark.parametrize("language", list(AppLanguage))
def test_operator_exports_review_without_mutating_project(qapp, tmp_path, monkeypatch, language):
    import json

    session = _session()
    session.dirty = False
    before = repr(session.project)
    dialog = LithologyMappingDialog(session, language=language)
    assert not dialog.export.isEnabled()
    _fill(dialog)
    dialog.review.click()
    assert dialog.export.isEnabled()
    target = tmp_path / "review"
    monkeypatch.setattr(QFileDialog, "getSaveFileName", lambda *args: (str(target), "JSON"))
    dialog.export.click()
    payload = json.loads(target.with_suffix(".json").read_text(encoding="utf-8"))
    assert payload["mapping"]["mapping_id"] == "review-1"
    assert dialog.export_status.text() == dialog._t("exported")
    assert dialog.export_status.textFormat() is Qt.TextFormat.PlainText
    assert not session.dirty and repr(session.project) == before
    dialog.fields["reviewer"].setText("Changed")
    assert not dialog.export.isEnabled() and not dialog.export_status.text()
    dialog.close()


def test_export_cancel_keeps_review_without_files(qapp, tmp_path, monkeypatch):
    dialog = LithologyMappingDialog(_session())
    _fill(dialog)
    dialog.review.click()
    mapping = dialog.mapping
    monkeypatch.setattr(QFileDialog, "getSaveFileName", lambda *args: ("", ""))
    dialog.export.click()
    assert dialog.mapping is mapping and not dialog.export_status.text()
    assert not list(tmp_path.iterdir())
    dialog.close()


@pytest.mark.parametrize("stage", ["before", "chooser"])
def test_export_rechecks_source_before_and_after_file_dialog(qapp, tmp_path, monkeypatch, stage):
    session = _session()
    dialog = LithologyMappingDialog(session)
    _fill(dialog)
    dialog.review.click()
    target = tmp_path / "review.json"
    called = []

    def choose(*args):
        called.append(True)
        session.current_well.lithology[0].description = "Changed"
        return str(target), "JSON"

    monkeypatch.setattr(QFileDialog, "getSaveFileName", choose)
    if stage == "before":
        session.current_well.lithology[0].description = "Changed"
    dialog.export.click()
    assert bool(called) == (stage == "chooser")
    assert not target.exists() and dialog.mapping is None
    assert not dialog.export.isEnabled()
    assert dialog.result_label.text() == dialog._t("invalid")
    dialog.close()


def test_export_io_error_is_localized_and_review_can_be_retried(qapp, tmp_path, monkeypatch):
    import geoworkbench.ui.lithology_mapping_dialog as module

    dialog = LithologyMappingDialog(_session())
    _fill(dialog)
    dialog.review.click()
    monkeypatch.setattr(QFileDialog, "getSaveFileName",
                        lambda *args: (str(tmp_path / "review.json"), "JSON"))

    def fail(*args, **kwargs):
        raise OSError("Internal secret path")

    monkeypatch.setattr(module, "export_lithology_review", fail)
    dialog.export.click()
    assert dialog.mapping is not None and dialog.export.isEnabled()
    assert dialog.export_status.text() == dialog._t("export_failed")
    assert "secret" not in dialog.export_status.text()
    dialog.close()


@pytest.mark.parametrize("language", list(AppLanguage))
def test_saved_record_view_does_not_activate_or_replace_current_mapping(qapp, tmp_path, monkeypatch, language):
    import json
    from geoworkbench.services.lithology_review_export import export_lithology_review
    from geoworkbench.ui.lithology_mapping_dialog import SavedLithologyReviewDialog

    session = _session()
    session.dirty = False
    dialog = LithologyMappingDialog(session, language=language)
    _fill(dialog)
    dialog.review.click()
    active = dialog.mapping
    target = tmp_path / "record.json"
    export_lithology_review(session, active, target)
    payload = json.loads(target.read_text(encoding="utf-8"))
    payload["mapping"]["reviewer"] = "<b>Unverified archived author</b>"
    payload["mapping"]["rock_family"] = "carbonate"
    target.write_text(json.dumps(payload), encoding="utf-8")
    monkeypatch.setattr(QFileDialog, "getOpenFileName", lambda *args: (str(target), "JSON"))
    seen = []

    def show(viewer):
        assert viewer.details.textFormat() is Qt.TextFormat.PlainText
        assert "<b>Unverified archived author</b>" in viewer.details.text()
        assert viewer.record.rock_family is RockFamily.CARBONATE
        assert viewer.record.source.source_sha256 in viewer.details.text()
        seen.append(viewer.record)
        return QDialog.DialogCode.Rejected

    monkeypatch.setattr(SavedLithologyReviewDialog, "exec", show)
    dialog.open_record.click()
    assert len(seen) == 1
    assert dialog.mapping is active and dialog.fields["reviewer"].text() == "Expert"
    assert dialog.family.currentData() == "halite" and not session.dirty
    dialog.close()


@pytest.mark.parametrize("choice", ["cancel", "malformed", "missing"])
def test_record_open_cancel_and_errors_leave_active_mapping_unchanged(qapp, tmp_path, monkeypatch, choice):
    dialog = LithologyMappingDialog(_session())
    _fill(dialog)
    dialog.review.click()
    active = dialog.mapping
    target = tmp_path / "record.json"
    if choice == "malformed":
        target.write_text('{"schema_version":999}', encoding="utf-8")
    monkeypatch.setattr(QFileDialog, "getOpenFileName",
                        lambda *args: ("" if choice == "cancel" else str(target), "JSON"))
    dialog.open_record.click()
    assert dialog.mapping is active and dialog.export.isEnabled()
    assert dialog.export_status.text() == ("" if choice == "cancel" else dialog._t("record_invalid"))
    dialog.close()
