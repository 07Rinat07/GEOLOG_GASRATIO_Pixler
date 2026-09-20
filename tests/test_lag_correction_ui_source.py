from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_lag_correction_dialog_exposes_versioned_workflow() -> None:
    source = (ROOT / "src/geoworkbench/ui/lag_correction_dialog.py").read_text(
        encoding="utf-8"
    )
    assert "class LagCorrectionDialog" in source
    assert "create_profile(" in source
    assert "add_revision(" in source
    assert "activate_revision(" in source
    assert "select_projection(" in source
    assert "LagCorrectionAxisMode.SOURCE" in source
    assert "LagCorrectionAxisMode.CORRECTED" in source
    assert 'setObjectName("lag-correction-preview")' in source


def test_main_window_wires_lag_correction_through_project_controller() -> None:
    source = (ROOT / "src/geoworkbench/ui/main_window.py").read_text(encoding="utf-8")
    start = source.index("def show_lag_correction")
    block = source[start : source.index("def show_time_depth_mapping", start)]

    assert "LagCorrectionProjectController(self.session)" in source
    assert 'self._localized_action("lag_correction.action")' in source
    assert "LagCorrectionDialog(" in source
    assert 'name="lag_correction"' in source
    assert "prepare_dialog_selection()" in block
    assert "restore_dialog_selection(selection)" in block
    assert "self.session.current_dataset_id =" not in block


def test_lag_correction_action_is_localized() -> None:
    import json

    for language in ("ru", "kk", "en"):
        payload = json.loads(
            (ROOT / f"src/geoworkbench/resources/i18n/{language}.json").read_text(
                encoding="utf-8"
            )
        )
        assert payload["lag_correction.action"]
        assert payload["lag_correction.source_missing"]
