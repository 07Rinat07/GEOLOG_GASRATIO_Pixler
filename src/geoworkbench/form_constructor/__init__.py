"""Core models for the universal form/header constructor.

This first slice intentionally contains no main-window integration.  It provides a
stable, testable asset registry and depth-anchored symbol model which later UI slices
can consume from Form Manager and the print renderer.
"""

from .asset_registry import AssetDefinition, ConstructorAssetRegistry, LocalizedName
from .depth_symbol import DepthSymbolPlacement
from .preview_revision import PreviewRevisionGate

__all__ = [
    "AssetDefinition",
    "ConstructorAssetRegistry",
    "DepthSymbolPlacement",
    "LocalizedName",
    "PreviewRevisionGate",
]
