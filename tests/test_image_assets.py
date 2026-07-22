import pytest

from geoworkbench.printing.image_assets import (
    ImageAssetError,
    create_png_asset,
    create_svg_asset,
    load_image_assets,
    save_image_assets,
)


PNG = b"\x89PNG\r\n\x1a\n" + b"safe-test-payload"
SVG = b'<svg xmlns="http://www.w3.org/2000/svg" width="20" height="10"><rect width="20" height="10" fill="#f00"/></svg>'


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


def test_svg_asset_round_trip_uses_svg_extension(tmp_path) -> None:
    source = tmp_path / "logo.svg"
    source.write_bytes(SVG)
    project = tmp_path / "well.geolog.json"
    asset = create_svg_asset(source)

    manifest = save_image_assets(project, {asset.asset_id: asset})
    restored = load_image_assets(project, manifest)

    assert restored[asset.asset_id].payload == SVG
    assert manifest[asset.asset_id]["media_type"] == "image/svg+xml"
    assert manifest[asset.asset_id]["path"].endswith(".svg")


@pytest.mark.parametrize(
    "payload",
    [
        b'<svg xmlns="http://www.w3.org/2000/svg"><script>alert(1)</script></svg>',
        b'<svg xmlns="http://www.w3.org/2000/svg" onload="alert(1)"/>',
        b'<svg xmlns="http://www.w3.org/2000/svg"><image href="https://example.test/x"/></svg>',
        b'<!DOCTYPE svg [<!ENTITY x SYSTEM "file:///etc/passwd">]><svg>&x;</svg>',
        b'<svg xmlns="http://www.w3.org/2000/svg"><rect style="fill:url(https://example.test/x)"/></svg>',
        b'<svg xmlns="http://www.w3.org/2000/svg"><foreignObject/></svg>',
    ],
)
def test_svg_asset_rejects_active_or_external_content(tmp_path, payload) -> None:
    source = tmp_path / "unsafe.svg"
    source.write_bytes(payload)

    with pytest.raises(ImageAssetError):
        create_svg_asset(source)


def test_image_asset_rejects_symlinked_storage_directory(tmp_path, symlink_or_skip) -> None:
    project = tmp_path / "well.geolog.json"
    outside = tmp_path / "outside"
    outside.mkdir()
    assets = tmp_path / "well.geolog.json.assets"
    assets.mkdir()
    symlink_or_skip(assets / "images", outside, target_is_directory=True)

    with pytest.raises(ImageAssetError):
        load_image_assets(project, {})


def test_image_asset_save_removes_only_orphaned_managed_png_files(
    tmp_path, symlink_or_skip
) -> None:
    source = tmp_path / "logo.png"
    source.write_bytes(PNG)
    project = tmp_path / "well.geolog.json"
    asset = create_png_asset(source)
    manifest = save_image_assets(project, {asset.asset_id: asset})
    managed = tmp_path / manifest[asset.asset_id]["path"]
    directory = managed.parent
    unrelated = directory / "notes.txt"
    unrelated.write_text("keep", encoding="utf-8")
    symlink = directory / ("f" * 64 + ".png")
    symlink_or_skip(symlink, unrelated)

    assert save_image_assets(project, {}) == {}

    assert not managed.exists()
    assert unrelated.read_text(encoding="utf-8") == "keep"
    assert symlink.is_symlink()
