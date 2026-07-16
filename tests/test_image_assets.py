import pytest

from geoworkbench.printing.image_assets import (
    ImageAssetError,
    create_png_asset,
    load_image_assets,
    save_image_assets,
)


PNG = b"\x89PNG\r\n\x1a\n" + b"safe-test-payload"


def test_image_asset_round_trip_uses_content_addressed_project_storage(tmp_path) -> None:
    source = tmp_path / "logo.png"
    source.write_bytes(PNG)
    project = tmp_path / "well.geolog.json"
    asset = create_png_asset(source)

    manifest = save_image_assets(project, {asset.asset_id: asset})
    restored = load_image_assets(project, manifest)

    assert restored[asset.asset_id].payload == PNG
    assert manifest[asset.asset_id]["path"].startswith("well.geolog.json.assets/images/")


def test_image_asset_rejects_non_png_and_path_escape(tmp_path) -> None:
    source = tmp_path / "logo.png"
    source.write_bytes(b"not png")
    with pytest.raises(ImageAssetError):
        create_png_asset(source)

    with pytest.raises(ImageAssetError):
        load_image_assets(
            tmp_path / "well.geolog.json",
            {
                "sha256:" + "0" * 64: {
                    "path": "../outside.png",
                    "sha256": "0" * 64,
                    "size_bytes": 1,
                    "media_type": "image/png",
                    "original_name": "logo.png",
                }
            },
        )


def test_image_asset_rejects_symlinked_storage_directory(tmp_path) -> None:
    project = tmp_path / "well.geolog.json"
    outside = tmp_path / "outside"
    outside.mkdir()
    assets = tmp_path / "well.geolog.json.assets"
    assets.mkdir()
    (assets / "images").symlink_to(outside, target_is_directory=True)

    with pytest.raises(ImageAssetError):
        load_image_assets(project, {})
