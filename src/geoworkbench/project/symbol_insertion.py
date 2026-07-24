from __future__ import annotations

from dataclasses import dataclass

from geoworkbench.form_constructor.asset_registry import AssetDefinition
from geoworkbench.project.annotation_schema import (
    AnnotationAnchor,
    AnnotationKind,
    AnnotationStyle,
)


@dataclass(frozen=True, slots=True)
class SymbolInsertionSelection:
    """Validated user choices required to create one catalog-symbol annotation."""

    symbol: AssetDefinition
    transparent_background: bool
    track_id: str
    parameter_mnemonic: str | None
    depth: float
    x_fraction: float
    offset_x: float
    offset_y: float
    width: float
    height: float

    def annotation_values(self, *, asset_ref: str) -> dict[str, object]:
        """Translate dialog choices into the existing annotation-controller contract."""

        parameter = self.parameter_mnemonic
        return {
            "kind": AnnotationKind.SYMBOL,
            "anchor": AnnotationAnchor.CURVE if parameter else AnnotationAnchor.DEPTH,
            "text": "",
            "track_id": self.track_id,
            "depth": self.depth,
            "parameter_mnemonic": parameter,
            "x_fraction": self.x_fraction,
            "offset_x": self.offset_x,
            "offset_y": self.offset_y,
            "width": self.width,
            "height": self.height,
            "style": AnnotationStyle(
                fill_opacity=0.0,
                border_width=0.0,
                padding=2.0,
                corner_radius=0.0,
                shadow=False,
            ),
            "asset_ref": asset_ref,
            "symbol_id": self.symbol.asset_id,
            "transparent_background": self.transparent_background,
            "visible": True,
            "locked": False,
            "print_enabled": True,
        }
