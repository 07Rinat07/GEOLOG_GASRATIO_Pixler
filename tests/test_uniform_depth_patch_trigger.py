from pathlib import Path


def test_uniform_depth_patch_is_applied_before_release() -> None:
    source = Path("src/geoworkbench/printing/auto_pagination.py").read_text(
        encoding="utf-8"
    )
    assert "_MIN_AUTO_BODY_HEIGHT_PX" not in source
