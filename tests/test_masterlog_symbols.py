from geoworkbench.printing.image_assets import SVG_MEDIA_TYPE, validate_image_asset
from geoworkbench.printing.masterlog_symbols import (
    BUILTIN_MASTERLOG_SYMBOLS,
    builtin_masterlog_symbol,
)


def test_builtin_masterlog_symbols_are_unique_safe_svg_assets() -> None:
    assert len(BUILTIN_MASTERLOG_SYMBOLS) >= 4
    assert len({item.symbol_id for item in BUILTIN_MASTERLOG_SYMBOLS}) == len(
        BUILTIN_MASTERLOG_SYMBOLS
    )
    asset_ids = set()
    for symbol in BUILTIN_MASTERLOG_SYMBOLS:
        asset = symbol.create_asset(symbol.symbol_id)
        validate_image_asset(asset.asset_id, asset)
        assert asset.media_type == SVG_MEDIA_TYPE
        asset_ids.add(asset.asset_id)
    assert len(asset_ids) == len(BUILTIN_MASTERLOG_SYMBOLS)


def test_builtin_masterlog_symbol_lookup_rejects_unknown_id() -> None:
    assert builtin_masterlog_symbol("core").symbol_id == "core"

    try:
        builtin_masterlog_symbol("unknown")
    except KeyError:
        pass
    else:
        raise AssertionError("Unknown symbol ID must be rejected")
