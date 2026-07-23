import json
from pathlib import Path

from PIL import Image


ROOT = Path(__file__).resolve().parents[1] / "resources" / "constructor_assets"


def test_factory_symbols_are_transparent_and_tightly_cropped() -> None:
    payload = json.loads((ROOT / "symbols/manifest.json").read_text(encoding="utf-8"))
    symbols = [item for item in payload["assets"] if item["kind"] == "depth_symbol"]
    assert {item["id"] for item in symbols} >= {
        "symbol-background-gas",
        "symbol-formation-gas",
        "symbol-tripping-gas",
        "symbol-test-gas",
    }
    for item in symbols:
        image = Image.open(ROOT / item["asset_path"]).convert("RGBA")
        alpha = image.getchannel("A")
        assert alpha.getextrema()[0] == 0
        assert alpha.getextrema()[1] >= 254
        assert alpha.getbbox() == (0, 0, *image.size)
        assert item.get("render", {}).get("transparent_background") is True
        assert item.get("render", {}).get("tight_crop") is True


def test_oil_show_symbols_do_not_keep_legacy_olive_canvas() -> None:
    payload = json.loads((ROOT / "symbols/manifest.json").read_text(encoding="utf-8"))
    by_id = {item["id"]: item for item in payload["assets"]}
    for symbol_id in {
        "symbol-oil-saturation",
        "symbol-residual-oil-saturation",
        "symbol-weak-oil-show",
    }:
        item = by_id[symbol_id]
        image = Image.open(ROOT / item["asset_path"]).convert("RGBA")
        assert all(image.getpixel(point)[3] == 0 for point in {
            (0, 0),
            (image.width - 1, 0),
            (0, image.height - 1),
            (image.width - 1, image.height - 1),
        })
        assert item["render"]["legacy_canvas_removed"] is True


def test_transparent_factory_symbols_are_included_in_wheel_package_data() -> None:
    pyproject = (ROOT.parents[1] / "pyproject.toml").read_text(encoding="utf-8")
    assert '"resources/constructor_assets/*/transparent/*.png"' in pyproject
