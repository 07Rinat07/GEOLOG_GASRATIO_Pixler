from __future__ import annotations

from dataclasses import dataclass
from functools import lru_cache
from importlib.resources import files
from pathlib import Path

from geoworkbench.form_constructor.asset_registry import ConstructorAssetRegistry


COMPACT_PATTERN_STYLE_NAMES: dict[str, str] = {
    "solid": "solid",
    "dots": "dense6",
    "dense_dots": "dense4",
    "sand_dots": "dense6",
    "sandstone_bricks": "backward_diagonal",
    "clay_dash": "horizontal",
    "silt_dash": "dense5",
    "gravel_circles": "dense7",
    "conglomerate": "diagonal_cross",
    "carbonate": "cross",
    "evaporite": "forward_diagonal",
    "coal": "dense1",
    "metamorphic": "diagonal_cross",
    "volcanic": "dense3",
}


LEGACY_BITMAP_PATTERN_ALIASES: dict[str, str] = {
    "clay_dash": "constructor:lithology-clay",
    "claystone_blocks": "constructor:lithology-claystone",
    "silt_dots": "constructor:lithology-silt",
    "siltstone_lines": "constructor:lithology-siltstone",
    "sand_dots": "constructor:lithology-sand",
    "sandstone_bricks": "constructor:lithology-sandstone",
    "gravel_circles": "constructor:lithology-gravelit",
    "conglomerate_pebbles": "constructor:lithology-conglomerate",
    "limestone_bricks": "constructor:lithology-limestone",
    "marl_ticks": "constructor:lithology-marl",
    "dolomite_rhombs": "constructor:lithology-dolomite",
    "anhydrite_chevrons": "constructor:lithology-anhydrite",
    "gypsum_arrows": "constructor:lithology-gypsum",
    "halite_crosses": "constructor:lithology-rock-salt",
    "coal_bands": "constructor:lithology-coal",
    "metamorphic_mesh": "constructor:lithology-metamorphic-rock",
    "volcanic_angles": "constructor:lithology-volcanic-rock",
}

CONSTRUCTOR_PATTERN_PREFIX = "constructor:"


@dataclass(frozen=True, slots=True)
class LithologyPatternDescriptor:
    requested_key: str
    resolved_key: str
    kind: str
    style_name: str | None = None
    asset_id: str | None = None
    asset_path: Path | None = None
    width_px: int | None = None
    height_px: int | None = None
    content_sha256: str | None = None


@lru_cache(maxsize=1)
def load_lithology_pattern_registry() -> ConstructorAssetRegistry:
    root = Path(str(files("geoworkbench").joinpath("resources/constructor_assets")))
    registry = ConstructorAssetRegistry.from_root(root)
    errors = registry.validate_files()
    if errors:
        raise RuntimeError("\n".join(errors))
    return registry


def resolve_lithology_pattern(pattern_key: str) -> LithologyPatternDescriptor:
    requested = str(pattern_key or "solid")
    resolved = LEGACY_BITMAP_PATTERN_ALIASES.get(requested, requested)
    if resolved.startswith(CONSTRUCTOR_PATTERN_PREFIX):
        asset_id = resolved.removeprefix(CONSTRUCTOR_PATTERN_PREFIX)
        try:
            asset = load_lithology_pattern_registry().get(asset_id)
        except (KeyError, OSError, RuntimeError, ValueError):
            return LithologyPatternDescriptor(
                requested_key=requested,
                resolved_key="solid",
                kind="hatch",
                style_name=COMPACT_PATTERN_STYLE_NAMES["solid"],
            )
        if asset.kind != "lithology_pattern":
            return LithologyPatternDescriptor(
                requested_key=requested,
                resolved_key="solid",
                kind="hatch",
                style_name=COMPACT_PATTERN_STYLE_NAMES["solid"],
            )
        return LithologyPatternDescriptor(
            requested_key=requested,
            resolved_key=resolved,
            kind="bitmap",
            asset_id=asset.asset_id,
            asset_path=asset.asset_path,
            width_px=asset.width_px,
            height_px=asset.height_px,
            content_sha256=asset.content_sha256,
        )
    style_name = COMPACT_PATTERN_STYLE_NAMES.get(
        resolved,
        COMPACT_PATTERN_STYLE_NAMES["solid"],
    )
    return LithologyPatternDescriptor(
        requested_key=requested,
        resolved_key=resolved if resolved in COMPACT_PATTERN_STYLE_NAMES else "solid",
        kind="hatch",
        style_name=style_name,
    )


def supported_pattern_keys() -> tuple[str, ...]:
    keys = list(COMPACT_PATTERN_STYLE_NAMES)
    keys.extend(LEGACY_BITMAP_PATTERN_ALIASES)
    try:
        keys.extend(
            f"{CONSTRUCTOR_PATTERN_PREFIX}{asset.asset_id}"
            for asset in load_lithology_pattern_registry().all(kind="lithology_pattern")
        )
    except (OSError, RuntimeError, ValueError):
        pass
    return tuple(dict.fromkeys(keys))
