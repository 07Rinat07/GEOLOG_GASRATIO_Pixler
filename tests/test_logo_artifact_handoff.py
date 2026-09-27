from __future__ import annotations

from pathlib import Path
import shutil


def test_copy_brand_logos_to_quality_artifact() -> None:
    root = Path(__file__).resolve().parents[1]
    source_dir = root / "src" / "geoworkbench" / "resources"
    output_dir = root / "build" / "ci-artifacts" / "quality" / "brand-logo-source"
    output_dir.mkdir(parents=True, exist_ok=True)

    for name in ("geologist-logo.png", "about-program-logo.png"):
        source = source_dir / name
        assert source.is_file()
        target = output_dir / name
        shutil.copyfile(source, target)
        assert target.stat().st_size == source.stat().st_size
