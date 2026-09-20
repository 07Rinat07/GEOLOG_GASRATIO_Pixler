from pathlib import Path


UI_ROOT = Path(__file__).resolve().parents[1] / "src" / "geoworkbench" / "ui"

# Public adapter: the actual QDialog implementation lives in the private module
# and is checked explicitly below.
_ADAPTER_EXEMPTIONS = {"unified_cuttings_sample_dialog.py"}


def test_top_level_dialog_modules_use_shared_work_area_contract() -> None:
    missing: list[str] = []
    for path in sorted(UI_ROOT.glob("*_dialog.py")):
        if path.name in _ADAPTER_EXEMPTIONS:
            continue
        source = path.read_text(encoding="utf-8")
        if "QDialog" not in source:
            continue
        if "fit_window_to_screen" not in source:
            missing.append(path.name)

    assert not missing, (
        "Top-level dialog modules must use fit_window_to_screen so taskbar/HiDPI "
        f"cannot hide primary actions: {missing}"
    )


def test_unified_cuttings_adapter_delegates_to_adaptive_implementation() -> None:
    implementation = (
        UI_ROOT / "_unified_cuttings_sample_dialog_impl.py"
    ).read_text(encoding="utf-8")

    assert "fit_window_to_screen" in implementation
    assert "QScrollArea" in implementation
    assert 'setObjectName("cuttings-dialog-buttons")' in implementation
