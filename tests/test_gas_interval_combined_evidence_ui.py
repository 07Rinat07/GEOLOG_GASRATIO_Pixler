"""Production gas interval handoff to explicit combined evidence preview."""

import numpy as np
import pytest
from PySide6.QtCore import QTimer, Qt
from PySide6.QtWidgets import QApplication, QComboBox, QDialog, QListWidgetItem, QMessageBox, QPushButton

from geoworkbench.domain.models import LithologyInterval
from geoworkbench.services.localization import AppLanguage
from geoworkbench.ui.gis_geology_evidence_dialog import GisGeologyEvidenceDialog
from test_gas_interval_gis_review_ui import _with_inserted_gis
from test_interpretation_geology_evidence_operator_ui import _workspace
from test_gis_interval_compare_ui import _wait_review
from test_gis_interval_compare_background import _paused_review


@pytest.mark.parametrize("language", list(AppLanguage))
@pytest.mark.parametrize("selected_index", (0, 1))
def test_combined_preview_is_explicit_same_md_and_read_only(
    qapp, monkeypatch, tmp_path, language, selected_index,
):
    workspace, session, receiver, dataset = _with_inserted_gis(monkeypatch, tmp_path, language)
    session.current_well.lithology = [LithologyInterval("lith-test", 100.0, 102.0, "limestone")]
    key = next(key for key, curve in dataset.curves.items() if curve.metadata.original_mnemonic == "GR")
    dataset.curves[key].values[1] = np.nan
    before = dataset.curves[key].values.copy()
    dirty = session.dirty
    seen = []

    def inspect(dialog):
        assert dialog.dataset is dataset
        assert dialog.bounds == ((100.0, 102.0) if selected_index == 0 else (101.0, 102.0))
        assert dialog.viewer.toPlainText() == ""
        dialog.review.click()
        assert dialog.status.text() == dialog.words[3]
        choice = next(
            dialog.curves.item(i) for i in range(dialog.curves.count())
            if dialog.curves.item(i).data(Qt.ItemDataRole.UserRole) == key
        )
        choice.setCheckState(Qt.CheckState.Checked)
        dialog.review.click()
        _wait_review(qapp, dialog)
        content = dialog.viewer.toPlainText()
        assert "lith-test" in content and key in content and "API" in content
        expected_bounds = "0.0–2.0" if selected_index == 0 else "2.0–2.0"
        assert expected_bounds in content
        choice.setCheckState(Qt.CheckState.Unchecked)
        assert dialog.viewer.toPlainText() == ""
        seen.append(True)
        return QDialog.DialogCode.Rejected

    monkeypatch.setattr(GisGeologyEvidenceDialog, "exec", inspect)
    try:
        workspace.geology_evidence_button.click()
        parent = workspace._geology_evidence_dialog
        parent.findChild(QComboBox, "interpretation-geology-evidence-select").setCurrentIndex(selected_index)
        parent.findChild(QPushButton, "interpretation-geology-combined-gis").click()
        assert seen == [True]
        assert receiver.curves == {} and session.dirty == dirty
        assert workspace._geology_pdf_evidence == () and workspace._geology_word_evidence == ()
        np.testing.assert_array_equal(dataset.curves[key].values, before)
        assert QApplication.overrideCursor() is None
    finally:
        workspace.close()


def test_combined_preview_rejects_changed_gas_candidate_after_open(qapp, monkeypatch, tmp_path):
    workspace, _, _, dataset = _with_inserted_gis(monkeypatch, tmp_path, AppLanguage.EN)
    messages = []
    monkeypatch.setattr(QMessageBox, "information", lambda *args: messages.append(args[2]))

    def inspect(dialog):
        dialog.curves.item(0).setCheckState(Qt.CheckState.Checked)
        dataset.curves["c1"].values[0] = 99.0
        dialog.review.click()
        assert not dialog.viewer.toPlainText()
        assert dialog.status.text() == dialog.words[4]
        assert not messages  # combined preview reports staleness inline
        return QDialog.DialogCode.Rejected

    monkeypatch.setattr(GisGeologyEvidenceDialog, "exec", inspect)
    try:
        workspace.geology_evidence_button.click()
        workspace._geology_evidence_dialog.findChild(
            QPushButton, "interpretation-geology-combined-gis",
        ).click()
        assert not messages
    finally:
        workspace.close()


def test_combined_preview_hidden_without_eligible_gis(qapp, monkeypatch):
    workspace, _ = _workspace(monkeypatch)
    try:
        workspace.geology_evidence_button.click()
        assert workspace._geology_evidence_dialog.findChild(
            QPushButton, "interpretation-geology-combined-gis",
        ).isHidden()
    finally:
        workspace.close()


def test_preview_rejects_more_than_eight_selected_curves(qapp, monkeypatch, tmp_path):
    from geoworkbench.ui import gis_interval_compare_worker as module

    workspace, session, _, dataset = _with_inserted_gis(monkeypatch, tmp_path, AppLanguage.EN)
    preview = GisGeologyEvidenceDialog(
        session, dataset, (100.0, 102.0), lambda: (100.0, 102.0),
        language=AppLanguage.EN,
    )
    monkeypatch.setattr(
        module, "review_gis_source_interval_batch",
        lambda *args, **kwargs: pytest.fail("Invalid selection must not run the review"),
    )
    try:
        for i in range(9):
            item = QListWidgetItem(f"extra-{i}")
            item.setData(Qt.ItemDataRole.UserRole, f"extra-{i}")
            item.setCheckState(Qt.CheckState.Checked)
            preview.curves.addItem(item)
        preview.review.click()
        assert preview.status.text() == preview.words[3]
        assert not preview.viewer.toPlainText()
    finally:
        if preview._worker is not None:
            _wait_review(qapp, preview)
        preview.close()
        workspace.close()


def test_preview_drops_completed_result_when_candidate_changes_during_review(
    qapp, monkeypatch, tmp_path,
):
    from geoworkbench.ui import gis_interval_compare_worker as module

    workspace, session, _, dataset = _with_inserted_gis(monkeypatch, tmp_path, AppLanguage.EN)
    valid = [True]
    preview = GisGeologyEvidenceDialog(
        session, dataset, (100.0, 102.0),
        lambda: (100.0, 102.0) if valid[0] else None,
        language=AppLanguage.EN,
    )
    original = module.review_gis_source_interval_batch

    def change_candidate(*args, **kwargs):
        result = original(*args, **kwargs)
        valid[0] = False
        return result

    monkeypatch.setattr(module, "review_gis_source_interval_batch", change_candidate)
    try:
        preview.curves.item(0).setCheckState(Qt.CheckState.Checked)
        preview.review.click()
        _wait_review(qapp, preview)
        assert preview.status.text() == preview.words[4]
        assert not preview.viewer.toPlainText()
        assert QApplication.overrideCursor() is None
    finally:
        preview.close()
        workspace.close()


@pytest.mark.parametrize("close", (False, True))
def test_combined_background_cancel_or_close_discards_results(qapp, monkeypatch, tmp_path, close):
    workspace, session, _, dataset = _with_inserted_gis(monkeypatch, tmp_path, AppLanguage.EN)
    started, release = _paused_review(monkeypatch)
    preview = GisGeologyEvidenceDialog(
        session, dataset, (100.0, 102.0), lambda: (100.0, 102.0),
        language=AppLanguage.EN,
    )
    preview.show()
    try:
        preview.curves.item(0).setCheckState(Qt.CheckState.Checked)
        preview.review.click()
        assert started.wait(5)
        from geoworkbench.ui.gis_interval_compare_dialog import _LIVE_WORKERS

        worker = preview._worker
        assert worker is not None and worker in _LIVE_WORKERS
        terminal = []

        def observe_terminal():
            # Direct observer runs after the registered GUI completion and
            # retirement slots, before DeferredDelete can destroy the emitter.
            terminal.append((preview._worker, worker in _LIVE_WORKERS,
                             preview._worker_cancel_connection))

        worker.finished.connect(observe_terminal, Qt.ConnectionType.DirectConnection)
        heartbeat = []
        QTimer.singleShot(0, lambda: heartbeat.append(True))
        qapp.processEvents()
        assert heartbeat == [True]
        assert not preview.curves.isEnabled() and not preview.review.isEnabled()
        if close:
            preview.close()
            assert preview.isVisible()
        else:
            preview.cancel.click()
        assert preview.status.text() == preview._t("cancelling")
        release.set()
        _wait_review(qapp, preview)
        assert terminal == [(None, False, None)]
        assert not preview.viewer.toPlainText()
        assert preview.status.text() == preview._t("cancelled")
        assert preview.curves.isEnabled()
        assert preview.isVisible() is not close
    finally:
        release.set()
        if preview._worker is not None:
            _wait_review(qapp, preview)
        preview.close()
        workspace.close()


@pytest.mark.parametrize("change", ("geology", "gis", "axis"))
def test_combined_background_rejects_changed_sources(qapp, monkeypatch, tmp_path, change):
    workspace, session, _, dataset = _with_inserted_gis(monkeypatch, tmp_path, AppLanguage.EN)
    started, release = _paused_review(monkeypatch)
    preview = GisGeologyEvidenceDialog(
        session, dataset, (100.0, 102.0), lambda: (100.0, 102.0),
        language=AppLanguage.EN,
    )
    try:
        item = preview.curves.item(0)
        key = item.data(Qt.ItemDataRole.UserRole)
        item.setCheckState(Qt.CheckState.Checked)
        preview.review.click()
        assert started.wait(5)
        if change == "geology":
            session.current_well.lithology.append(
                LithologyInterval("new-lith", 100.0, 102.0, "sandstone"),
            )
        elif change == "gis":
            dataset.curves[key].values[0] = 99.0
        else:
            dataset.active_index.values[0] = 99.0
        release.set()
        _wait_review(qapp, preview)
        assert preview.status.text() == preview.words[4]
        assert not preview.viewer.toPlainText()
    finally:
        release.set()
        if preview._worker is not None:
            _wait_review(qapp, preview)
        preview.close()
        workspace.close()


def test_combined_rechecks_arrays_after_worker_verification(qapp, monkeypatch, tmp_path):
    from geoworkbench.services.gis_interval_sample_review import review_gis_source_interval_batch
    from geoworkbench.services.gis_interval_snapshot import GisIntervalSnapshot

    workspace, session, _, dataset = _with_inserted_gis(monkeypatch, tmp_path, AppLanguage.EN)
    preview = GisGeologyEvidenceDialog(
        session, dataset, (100.0, 102.0), lambda: (100.0, 102.0),
        language=AppLanguage.EN,
    )
    try:
        item = preview.curves.item(0)
        key = item.data(Qt.ItemDataRole.UserRole)
        item.setCheckState(Qt.CheckState.Checked)
        preview._keys = (key,)
        preview._geology = preview._read_geology()
        snapshot = GisIntervalSnapshot(dataset, (key,), lambda: False)
        payload = review_gis_source_interval_batch(
            snapshot.dataset, curve_keys=(key,), top_md_m=100.0, bottom_md_m=102.0,
        )
        assert snapshot.matches(lambda: False)
        dataset.curves[key].values[0] = 99.0
        assert snapshot.structure_matches()
        preview._completed(snapshot, payload)
        assert preview.status.text() == preview.words[4]
        assert not preview.viewer.toPlainText()
    finally:
        preview.close()
        workspace.close()


def test_combined_repeated_open_review_close_keeps_workers_retired(qapp, monkeypatch, tmp_path):
    """Exercise native lifetime in one process, across languages and dialogs."""
    from PySide6.QtCore import QCoreApplication, QEvent
    from geoworkbench.ui.gis_interval_compare_dialog import _LIVE_WORKERS

    workspace, session, _, dataset = _with_inserted_gis(monkeypatch, tmp_path, AppLanguage.EN)
    before = set(_LIVE_WORKERS)
    key = next(key for key, curve in dataset.curves.items()
               if curve.metadata.original_mnemonic == "GR")
    source = dataset.curves[key].values.copy()
    try:
        for language in list(AppLanguage) * 4:
            dialog = GisGeologyEvidenceDialog(
                session, dataset, (100.0, 102.0), lambda: (100.0, 102.0),
                language=language,
            )
            try:
                choice = next(
                    dialog.curves.item(i) for i in range(dialog.curves.count())
                    if dialog.curves.item(i).data(Qt.ItemDataRole.UserRole) == key
                )
                choice.setCheckState(Qt.CheckState.Checked)
                for _ in range(2):
                    dialog.review.click()
                    worker = dialog._worker
                    assert worker is not None and worker in _LIVE_WORKERS
                    _wait_review(qapp, dialog)
                    assert dialog.status.text() == dialog._t("complete")
                    assert key in dialog.viewer.toPlainText()
                    assert dialog._worker_cancel_connection is None
                    assert set(_LIVE_WORKERS) == before
            finally:
                if dialog._worker is not None:
                    _wait_review(qapp, dialog)
                dialog.close()
                dialog.deleteLater()
                QCoreApplication.sendPostedEvents(dialog, QEvent.Type.DeferredDelete)
        np.testing.assert_array_equal(dataset.curves[key].values, source)
    finally:
        workspace.close()
