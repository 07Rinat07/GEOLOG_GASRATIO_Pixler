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


@pytest.mark.parametrize("language", list(AppLanguage))
def test_history_view_is_read_only_and_details_recheck_current_source(qapp, tmp_path, monkeypatch, language):
    from geoworkbench.services.lithology_review_reader import ReviewSourceStatus
    from geoworkbench.ui.lithology_mapping_dialog import (
        LithologyReviewHistoryDialog, SavedLithologyReviewDialog,
    )
    from test_lithology_review_history import _history_files

    session, first, second = _history_files(tmp_path)
    session.dirty = False
    dialog = LithologyMappingDialog(session, language=language)
    _fill(dialog)
    dialog.review.click()
    active = dialog.mapping
    monkeypatch.setattr(QFileDialog, "getOpenFileNames",
                        lambda *args: ([str(second), str(first)], "JSON"))
    observed = []

    def details(viewer):
        assert viewer.record.mapping_id == "review-1"
        assert viewer.status is ReviewSourceStatus.DIFFERENT
        observed.append(viewer.record)
        return QDialog.DialogCode.Rejected

    def history(viewer):
        from PySide6.QtWidgets import QAbstractItemView

        assert viewer.table.rowCount() == 2
        assert viewer.table.item(0, 1).text() == "review-1"
        assert viewer.table.item(1, 1).text() == "review-2"
        assert viewer.table.editTriggers() == QAbstractItemView.EditTrigger.NoEditTriggers
        assert not viewer.table.selectionModel().selectedRows()
        assert not viewer.details.isEnabled()
        assert dialog.mapping is active
        viewer.table.selectRow(0)
        assert viewer.details.isEnabled()
        session.current_well.lithology[0].description = "Changed while viewing"
        viewer.details.click()
        return QDialog.DialogCode.Rejected

    monkeypatch.setattr(SavedLithologyReviewDialog, "exec", details)
    monkeypatch.setattr(LithologyReviewHistoryDialog, "exec", history)
    dialog.open_history.click()
    assert len(observed) == 1
    assert dialog.mapping is None and dialog.fields["reviewer"].text() == "Expert"
    assert not session.dirty
    dialog.close()


@pytest.mark.parametrize("choice", ["cancel", "bad_file", "too_many"])
def test_history_cancel_or_invalid_selection_preserves_active_review(qapp, tmp_path, monkeypatch, choice):
    dialog = LithologyMappingDialog(_session())
    _fill(dialog)
    dialog.review.click()
    active = dialog.mapping
    target = tmp_path / "bad.json"
    target.write_text("null", encoding="utf-8")
    paths = [] if choice == "cancel" else [str(target)] * (17 if choice == "too_many" else 1)
    monkeypatch.setattr(QFileDialog, "getOpenFileNames", lambda *args: (paths, "JSON"))
    dialog.open_history.click()
    assert dialog.mapping is active and dialog.export.isEnabled()
    assert dialog.export_status.text() == ("" if choice == "cancel" else dialog._t("history_invalid"))
    dialog.close()


@pytest.mark.parametrize("language", list(AppLanguage))
def test_history_compare_two_explicit_rows_without_approval_or_project_writes(
    qapp, tmp_path, monkeypatch, language,
):
    import json
    from PySide6.QtCore import QItemSelectionModel
    from PySide6.QtWidgets import QAbstractItemView
    from geoworkbench.ui.lithology_mapping_dialog import (
        LithologyReviewComparisonDialog, LithologyReviewHistoryDialog,
    )
    from test_lithology_review_history import _history_files

    session, first, second = _history_files(tmp_path)
    payload = json.loads(second.read_text(encoding="utf-8"))
    payload["mapping"]["reviewer"] = "<b>Unverified reviewer</b>"
    second.write_text(json.dumps(payload), encoding="utf-8")
    session.dirty = False
    before = repr(session.project)
    dialog = LithologyMappingDialog(session, language=language)
    monkeypatch.setattr(QFileDialog, "getOpenFileNames",
                        lambda *args: ([str(second), str(first)], "JSON"))
    comparisons = []

    def inspect_comparison(viewer):
        assert viewer.comparison.first.mapping_id == "review-1"
        assert viewer.comparison.second.mapping_id == "review-2"
        assert viewer.table is not None
        assert viewer.table.editTriggers() == QAbstractItemView.EditTrigger.NoEditTriggers
        fields = {viewer.table.item(row, 0).text(): row
                  for row in range(viewer.table.rowCount())}
        assert len(fields) == 2
        assert any(viewer.table.item(row, 2).text() == "<b>Unverified reviewer</b>"
                   for row in fields.values())
        assert viewer.table.item(0, 0).text() != "lithology_mapping.comparison_field.mapping_id"
        comparisons.append(viewer.comparison)
        return QDialog.DialogCode.Rejected

    def inspect_history(viewer):
        assert not viewer.compare.isEnabled() and not viewer.details.isEnabled()
        viewer.table.selectRow(0)
        assert viewer.details.isEnabled() and not viewer.compare.isEnabled()
        viewer.table.selectionModel().select(
            viewer.table.model().index(1, 0),
            QItemSelectionModel.SelectionFlag.Select | QItemSelectionModel.SelectionFlag.Rows,
        )
        assert viewer.compare.isEnabled() and not viewer.details.isEnabled()
        viewer.compare.click()
        return QDialog.DialogCode.Rejected

    monkeypatch.setattr(LithologyReviewComparisonDialog, "exec", inspect_comparison)
    monkeypatch.setattr(LithologyReviewHistoryDialog, "exec", inspect_history)
    dialog.open_history.click()
    assert len(comparisons) == 1
    assert repr(session.project) == before and not session.dirty
    dialog.close()


def test_history_identical_assertions_are_not_auto_approved(qapp, tmp_path, monkeypatch):
    import json
    from PySide6.QtCore import QItemSelectionModel
    from geoworkbench.ui.lithology_mapping_dialog import (
        LithologyReviewComparisonDialog, LithologyReviewHistoryDialog,
    )
    from test_lithology_review_history import _history_files

    session, first, second = _history_files(tmp_path)
    payload = json.loads(first.read_text(encoding="utf-8"))
    payload["recorded_at_utc"] = "2026-10-22T11:00:00Z"
    second.write_text(json.dumps(payload), encoding="utf-8")
    dialog = LithologyMappingDialog(session)
    monkeypatch.setattr(QFileDialog, "getOpenFileNames",
                        lambda *args: ([str(first), str(second)], "JSON"))

    def inspect_comparison(viewer):
        assert not viewer.comparison.differences
        assert viewer.table is None
        return QDialog.DialogCode.Rejected

    def inspect_history(viewer):
        viewer.table.selectRow(0)
        viewer.table.selectionModel().select(
            viewer.table.model().index(1, 0),
            QItemSelectionModel.SelectionFlag.Select | QItemSelectionModel.SelectionFlag.Rows,
        )
        assert viewer.compare.isEnabled()
        viewer.compare.click()
        return QDialog.DialogCode.Rejected

    monkeypatch.setattr(LithologyReviewComparisonDialog, "exec", inspect_comparison)
    monkeypatch.setattr(LithologyReviewHistoryDialog, "exec", inspect_history)
    dialog.open_history.click()
    dialog.close()


@pytest.mark.parametrize("language", list(AppLanguage))
def test_revision_proposal_preview_requires_explicit_baseline_and_never_approves(
    qapp, tmp_path, language,
):
    from PySide6.QtWidgets import QAbstractItemView
    from geoworkbench.services.lithology_review_reader import load_lithology_review
    from geoworkbench.ui.lithology_mapping_dialog import LithologyRevisionProposalDialog
    from test_lithology_review_history import _history_files

    session, first_path, second_path = _history_files(tmp_path)
    first, second = load_lithology_review(first_path), load_lithology_review(second_path)
    session.dirty = False
    original = repr(session.project)

    dialog = LithologyRevisionProposalDialog(first, second, session=session, language=language)
    assert dialog.baseline.currentData() is None
    assert dialog.proposal is None
    assert dialog.preview.isHidden()
    assert dialog.summary.textFormat() == Qt.TextFormat.PlainText
    assert dialog._t("proposal_action") != "lithology_mapping.proposal_action"
    dialog.proposal_id.setText("proposal-42")
    dialog.proposed_by.setText("<b>Unverified operator</b>")
    dialog.justification.setPlainText("Request a geology review; not approval")
    dialog.prepare.click()
    assert dialog.proposal is None
    assert dialog.summary.text() == dialog._t("proposal_invalid")

    # The operator must explicitly choose a baseline. Time order is not authority.
    dialog.baseline.setCurrentIndex(2)
    dialog.prepare.click()
    proposal = dialog.proposal
    assert proposal is not None
    assert proposal.review_state == "proposal_not_geological_approval"
    assert proposal.comparison.first.mapping_id == "review-2"
    assert proposal.comparison.second.mapping_id == "review-1"
    assert proposal.proposed_by == "<b>Unverified operator</b>"
    assert dialog.preview.rowCount() == 1
    assert dialog.preview.item(0, 1).text() == "review-2"
    assert dialog.preview.item(0, 2).text() == "review-1"
    assert dialog.preview.editTriggers() == QAbstractItemView.EditTrigger.NoEditTriggers
    assert "proposal-42" in dialog.summary.text()
    assert dialog._t("proposal_unapproved") in dialog.summary.text()
    assert dialog.source_warning.textFormat() == Qt.TextFormat.PlainText
    assert not dialog.source_warning.text()  # Both archived sources still match.
    assert not dialog.preview.isHidden()

    dialog.justification.setPlainText("Edited explanation")
    assert dialog.proposal is None and dialog.preview.rowCount() == 0
    assert dialog.summary.text() == ""
    assert not session.dirty and repr(session.project) == original
    dialog.close()


def test_revision_proposal_preview_rejects_identical_assertions_and_long_reason(qapp, tmp_path):
    from dataclasses import replace
    from geoworkbench.services.lithology_review_reader import load_lithology_review
    from geoworkbench.ui.lithology_mapping_dialog import LithologyRevisionProposalDialog
    from test_lithology_review_history import _history_files

    session, first_path, second_path = _history_files(tmp_path)
    first, second = load_lithology_review(first_path), load_lithology_review(second_path)
    identical = replace(first, recorded_at_utc="2026-10-22T23:00:00Z")
    original = repr(session.project)
    dialog = LithologyRevisionProposalDialog(first, identical, session=session)
    dialog.baseline.setCurrentIndex(1)
    dialog.proposal_id.setText("proposal-43")
    dialog.proposed_by.setText("Operator")
    dialog.justification.setPlainText("Check proposed revision")
    dialog.prepare.click()
    assert dialog.proposal is None
    assert dialog.summary.text() == dialog._t("proposal_invalid")
    dialog.close()

    dialog = LithologyRevisionProposalDialog(first, second, session=session)
    dialog.baseline.setCurrentIndex(1)
    dialog.proposal_id.setText("proposal-44")
    dialog.proposed_by.setText("Operator")
    dialog.justification.setPlainText("x" * 4097)
    dialog.prepare.click()
    assert dialog.proposal is None
    assert dialog.summary.text() == dialog._t("proposal_invalid")
    assert repr(session.project) == original
    dialog.close()


@pytest.mark.parametrize("language", list(AppLanguage))
def test_history_proposal_action_requires_two_rows_and_no_default_baseline(
    qapp, tmp_path, monkeypatch, language,
):
    from PySide6.QtCore import QItemSelectionModel
    from geoworkbench.services.lithology_review_history import load_lithology_review_history
    from geoworkbench.ui.lithology_mapping_dialog import (
        LithologyReviewHistoryDialog, LithologyRevisionProposalDialog,
    )
    from test_lithology_review_history import _history_files

    session, first_path, second_path = _history_files(tmp_path)
    entries = load_lithology_review_history(session, (first_path, second_path))
    before = repr(session.project)
    session.dirty = False
    history = LithologyReviewHistoryDialog(session, entries, language=language)
    calls = []

    def inspect_proposal(view):
        assert view.baseline.currentData() is None
        assert view.proposal is None
        assert view.records[0].mapping_id == "review-1"
        assert view.records[1].mapping_id == "review-2"
        calls.append(view)
        return QDialog.DialogCode.Rejected

    monkeypatch.setattr(LithologyRevisionProposalDialog, "exec", inspect_proposal)
    assert not history.propose.isEnabled()
    history.table.selectRow(0)
    assert not history.propose.isEnabled()
    history.table.selectionModel().select(
        history.table.model().index(1, 0),
        QItemSelectionModel.SelectionFlag.Select | QItemSelectionModel.SelectionFlag.Rows,
    )
    assert history.propose.isEnabled()
    history.propose.click()
    assert len(calls) == 1
    history.table.clearSelection()
    assert not history.propose.isEnabled()
    assert not session.dirty and repr(session.project) == before
    history.close()


@pytest.mark.parametrize("language", list(AppLanguage))
def test_proposal_preflight_rechecks_both_archival_sources_without_approval(
    qapp, tmp_path, language,
):
    from dataclasses import replace
    from geoworkbench.services.lithology_review_reader import load_lithology_review
    from geoworkbench.ui.lithology_mapping_dialog import LithologyRevisionProposalDialog
    from test_lithology_review_history import _history_files

    session, first_path, second_path = _history_files(tmp_path)
    first = load_lithology_review(first_path)
    second = load_lithology_review(second_path)
    second = replace(second, source=replace(second.source, source_sha256="0" * 64))
    session.dirty = False
    before = repr(session.project)
    dialog = LithologyRevisionProposalDialog(first, second, session=session, language=language)
    assert dialog.source_status.textFormat() == Qt.TextFormat.PlainText
    assert dialog.source_warning.textFormat() == Qt.TextFormat.PlainText
    assert not dialog.source_status.text()
    assert not dialog.source_warning.text()
    assert "lithology_mapping.proposal_source_warning" in Localizer.create(language).catalog
    assert "lithology_mapping.proposal_source_preflight" in Localizer.create(
        language,
    ).catalog

    # Reversed baseline proves statuses follow the operator's choice, not UTC order.
    dialog.baseline.setCurrentIndex(2)
    dialog.proposal_id.setText("proposal-source-preflight")
    dialog.proposed_by.setText("<b>Unverified</b>")
    dialog.justification.setPlainText("Please check source identity before geology review")
    dialog.prepare.click()
    assert dialog.proposal is not None
    assert dialog.proposal.review_state == "proposal_not_geological_approval"
    assert dialog.source_status.text() == dialog._t(
        "proposal_source_preflight",
        baseline=dialog._t("record_status.different"),
        candidate=dialog._t("record_status.matching"),
    )
    assert dialog.source_warning.text() == dialog._t("proposal_source_warning")
    assert dialog._t("proposal_unapproved") in dialog.summary.text()
    assert repr(session.project) == before and not session.dirty

    # The history table's old source status must not be reused after source edits.
    session.current_well.lithology[0].description = "Source changed during preview"
    dialog.prepare.click()
    assert dialog.proposal is not None
    assert dialog.source_status.text() == dialog._t(
        "proposal_source_preflight",
        baseline=dialog._t("record_status.different"),
        candidate=dialog._t("record_status.different"),
    )
    assert dialog.source_warning.text() == dialog._t("proposal_source_warning")

    session.current_well.lithology.clear()
    dialog.prepare.click()
    assert dialog.proposal is not None  # An unapproved archival suggestion, not activation.
    assert dialog.source_status.text() == dialog._t(
        "proposal_source_preflight",
        baseline=dialog._t("record_status.unavailable"),
        candidate=dialog._t("record_status.unavailable"),
    )
    assert dialog.source_warning.text() == dialog._t("proposal_source_warning")
    dialog.proposal_id.setText("edited")
    assert dialog.proposal is None
    assert dialog.source_status.text() == ""
    assert dialog.source_warning.text() == ""
    assert dialog.preview.rowCount() == 0
    dialog.close()


@pytest.mark.parametrize("language", list(AppLanguage))
def test_unrelated_project_proposal_preflight_warns_without_authorizing(
    qapp, tmp_path, language,
):
    from dataclasses import replace
    from geoworkbench.services.lithology_review_reader import load_lithology_review
    from geoworkbench.ui.lithology_mapping_dialog import LithologyRevisionProposalDialog
    from test_lithology_review_history import _history_files

    session, baseline_path, candidate_path = _history_files(tmp_path)
    baseline = replace(load_lithology_review(baseline_path), project_id="other-project")
    candidate = replace(load_lithology_review(candidate_path), project_id="other-project")
    session.dirty = False
    original = repr(session.project)

    dialog = LithologyRevisionProposalDialog(
        baseline, candidate, session=session, language=language,
    )
    dialog.baseline.setCurrentIndex(1)
    dialog.proposal_id.setText("operator-diagnostic")
    dialog.proposed_by.setText("Unverified initiator")
    dialog.justification.setPlainText("Manual source investigation required")
    dialog.prepare.click()

    assert dialog.proposal is not None  # Detached proposal, never active.
    assert dialog.proposal.review_state == "proposal_not_geological_approval"
    assert dialog.source_status.text() == dialog._t(
        "proposal_source_preflight",
        baseline=dialog._t("record_status.other_project"),
        candidate=dialog._t("record_status.other_project"),
    )
    assert dialog.source_warning.text() == dialog._t("proposal_source_warning")
    assert not session.dirty and repr(session.project) == original

    dialog.baseline.setCurrentIndex(2)
    assert dialog.proposal is None and not dialog.source_warning.text()
    assert not dialog.source_status.text()
    dialog.close()
