from __future__ import annotations

from base64 import b64encode
from dataclasses import dataclass
from hashlib import sha256
from html import escape
import json
from pathlib import Path
from typing import Any, Mapping

from geoworkbench.project.annotation_schema import (
    AnnotationAnchor,
    AnnotationKind,
    AnnotationRecord,
    AnnotationStyle,
)
from geoworkbench.project.lithotype_catalog_models import CatalogLithotype
from geoworkbench.tablet.annotation_layout import AnnotationLayout, LayoutRect, layout_annotation
from geoworkbench.tablet.grid_geometry import (
    engineering_tick_levels,
    normalized_grid_lines,
    project_grid_lines,
)
from geoworkbench.tablet.lithology_legend import build_lithology_legend_from_ids
from geoworkbench.tablet.lithology_pattern_catalog import resolve_lithology_pattern


GOLDEN_SCHEMA = "geoworkbench.render-golden/v1"
REFERENCE_DPI = 96.0
PX_TO_MM = 25.4 / REFERENCE_DPI


@dataclass(frozen=True, slots=True)
class GoldenFixtureDocument:
    fixture_id: str
    payload: Mapping[str, Any]

    def as_dict(self) -> dict[str, Any]:
        normalized = _normalize(self.payload)
        return {
            "schema": GOLDEN_SCHEMA,
            "fixture_id": self.fixture_id,
            "payload_sha256": sha256(_canonical_bytes(normalized)).hexdigest(),
            "payload": normalized,
        }


def build_golden_documents() -> dict[str, GoldenFixtureDocument]:
    return {
        "grid_screen_print_v1.json": GoldenFixtureDocument(
            "grid.screen-print.standard.v1",
            _grid_payload(),
        ),
        "legend_multilingual_v1.json": GoldenFixtureDocument(
            "legend.multilingual.standard.v1",
            _legend_payload(),
        ),
        "lithotype_patterns_v1.json": GoldenFixtureDocument(
            "lithotype.patterns.standard.v1",
            _lithotype_payload(),
        ),
        "annotations_screen_print_v1.json": GoldenFixtureDocument(
            "annotations.screen-print.standard.v1",
            _annotation_payload(),
        ),
    }


def write_golden_fixtures(directory: str | Path) -> tuple[Path, ...]:
    target = Path(directory)
    target.mkdir(parents=True, exist_ok=True)
    written: list[Path] = []
    documents = build_golden_documents()
    for filename, document in documents.items():
        path = target / filename
        path.write_text(_json_text(document.as_dict()), encoding="utf-8")
        written.append(path)
    screen_svg = target / "screen_tablet_v1.svg"
    screen_svg.write_text(_render_surface_svg("screen"), encoding="utf-8")
    written.append(screen_svg)
    print_svg = target / "print_masterlog_v1.svg"
    print_svg.write_text(_render_surface_svg("print"), encoding="utf-8")
    written.append(print_svg)
    return tuple(written)


def verify_golden_fixture(path: str | Path) -> tuple[str, ...]:
    source = Path(path)
    try:
        document = json.loads(source.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        return (f"cannot read golden fixture {source}: {exc}",)
    errors: list[str] = []
    if document.get("schema") != GOLDEN_SCHEMA:
        errors.append(f"unsupported golden schema: {document.get('schema')!r}")
    payload = _normalize(document.get("payload"))
    actual = sha256(_canonical_bytes(payload)).hexdigest()
    if document.get("payload_sha256") != actual:
        errors.append(
            f"payload checksum mismatch: expected {document.get('payload_sha256')}, got {actual}"
        )
    return tuple(errors)


def expected_golden_files() -> tuple[str, ...]:
    return (*build_golden_documents().keys(), "screen_tablet_v1.svg", "print_masterlog_v1.svg")


def _grid_payload() -> dict[str, Any]:
    major = 4
    minor = 5
    screen = LayoutRect(60.0, 80.0, 700.0, 1180.0)
    printed = LayoutRect(15.0, 20.0, 150.0, 230.0)
    signature = [
        {"fraction": line.fraction, "major": line.major}
        for line in normalized_grid_lines(major, minor)
    ]
    return {
        "contract_version": 1,
        "major_divisions": major,
        "minor_divisions": minor,
        "alpha": 0.24,
        "minor_alpha_factor": 0.45,
        "normalized_signature": signature,
        "screen": {
            "unit": "px",
            "rect": _rect_dict(screen),
            "x_axis_range": [0.0, 200.0],
            "y_axis_range": [1200.0, 1400.0],
            "x_tick_levels": engineering_tick_levels(0.0, 200.0, major, minor),
            "y_tick_levels": engineering_tick_levels(1200.0, 1400.0, major, minor),
            "x_lines": _projected_lines(screen.left, screen.width, major, minor),
            "y_lines": _projected_lines(screen.top, screen.height, major, minor),
        },
        "print": {
            "unit": "mm",
            "reference_dpi": REFERENCE_DPI,
            "rect": _rect_dict(printed),
            "x_lines": _projected_lines(printed.left, printed.width, major, minor),
            "y_lines": _projected_lines(printed.top, printed.height, major, minor),
            "major_pen_mm": 0.2,
            "minor_pen_mm": 0.1,
        },
    }


def _legend_payload() -> dict[str, Any]:
    catalog = _golden_catalog()
    ids = ("sandstone", "clay", "sandstone", "legacy_rock", "dolomite")
    unknown = {"legacy_rock": "Legacy breccia / Наследованная брекчия"}
    names = {
        "ru": "Неизвестный литотип",
        "kk": "Белгісіз литотип",
        "en": "Unknown lithotype",
    }
    entries: dict[str, list[dict[str, Any]]] = {}
    for language in ("ru", "kk", "en"):
        resolved = build_lithology_legend_from_ids(
            ids,
            catalog,
            name_resolver=lambda item, selected=language: item.localized_name(selected),
            unknown_name=names[language],
            unknown_descriptions=unknown,
        )
        entries[language] = [
            {
                "lithotype_id": item.lithotype_id,
                "code": item.code,
                "name": item.name,
                "color": item.color,
                "pattern_key": item.pattern_key,
            }
            for item in resolved
        ]
    return {
        "contract_version": 1,
        "selection_order": list(ids),
        "deduplication": "first occurrence",
        "unknown_color": "#b0b0b0",
        "entries": entries,
    }


def _lithotype_payload() -> dict[str, Any]:
    requested = (
        "solid",
        "carbonate",
        "sandstone_bricks",
        "constructor:lithology-clay",
        "unknown-pattern",
    )
    entries: list[dict[str, Any]] = []
    for key in requested:
        descriptor = resolve_lithology_pattern(key)
        item: dict[str, Any] = {
            "requested_key": descriptor.requested_key,
            "resolved_key": descriptor.resolved_key,
            "kind": descriptor.kind,
            "style_name": descriptor.style_name,
            "asset_id": descriptor.asset_id,
            "width_px": descriptor.width_px,
            "height_px": descriptor.height_px,
            "content_sha256": descriptor.content_sha256,
        }
        if descriptor.kind == "bitmap" and descriptor.width_px and descriptor.height_px:
            item["screen_tile_px"] = [descriptor.width_px, descriptor.height_px]
            item["print_tile_mm_at_96dpi"] = [
                descriptor.width_px * PX_TO_MM,
                descriptor.height_px * PX_TO_MM,
            ]
        entries.append(item)
    return {
        "contract_version": 1,
        "reference_dpi": REFERENCE_DPI,
        "fallback": "solid",
        "patterns": entries,
    }


def _annotation_payload() -> dict[str, Any]:
    records = _golden_annotations()
    screen_bounds = LayoutRect(60.0, 80.0, 700.0, 1180.0)
    print_bounds = LayoutRect(15.0, 20.0, 150.0, 230.0)
    anchor_fractions = {
        "callout-gas": (0.28, 0.20),
        "warning-rotated": (0.74, 0.44),
        "comment-note": (0.42, 0.68),
        "value-edge": (0.97, 0.93),
    }
    entries: list[dict[str, Any]] = []
    for record in records:
        x_fraction, y_fraction = anchor_fractions[record.annotation_id]
        screen_anchor = (
            screen_bounds.left + screen_bounds.width * x_fraction,
            screen_bounds.top + screen_bounds.height * y_fraction,
        )
        print_anchor = (
            print_bounds.left + print_bounds.width * x_fraction,
            print_bounds.top + print_bounds.height * y_fraction,
        )
        screen_layout = layout_annotation(
            record,
            anchor_x=screen_anchor[0],
            anchor_y=screen_anchor[1],
            bounds=screen_bounds,
            pixel_scale=1.0,
            visible_margin=20.0,
            max_width=screen_bounds.width,
            max_height=screen_bounds.height,
        )
        print_layout = layout_annotation(
            record,
            anchor_x=print_anchor[0],
            anchor_y=print_anchor[1],
            bounds=print_bounds,
            pixel_scale=PX_TO_MM,
            visible_margin=4.0,
            max_width=print_bounds.width,
            max_height=print_bounds.height,
        )
        entries.append(
            {
                "annotation_id": record.annotation_id,
                "kind": record.kind.value,
                "rotation_degrees": record.style.rotation,
                "text": record.text,
                "screen": _annotation_layout_dict(screen_layout, "px"),
                "print": _annotation_layout_dict(print_layout, "mm"),
            }
        )
    return {
        "contract_version": 1,
        "reference_dpi": REFERENCE_DPI,
        "pixel_to_mm": PX_TO_MM,
        "screen_bounds": _rect_dict(screen_bounds),
        "print_bounds": _rect_dict(print_bounds),
        "annotations": entries,
    }


def _golden_catalog() -> tuple[CatalogLithotype, ...]:
    return (
        CatalogLithotype(
            "sandstone",
            "SS",
            "Песчаник",
            "Sandstone",
            "sedimentary",
            "#e7cf8b",
            "sandstone_bricks",
            True,
            name_kk="Құмтас",
        ),
        CatalogLithotype(
            "clay",
            "CL",
            "Глина",
            "Clay",
            "sedimentary",
            "#9ca3af",
            "clay_dash",
            True,
            name_kk="Саз",
        ),
        CatalogLithotype(
            "dolomite",
            "DL",
            "Доломит",
            "Dolomite",
            "carbonate",
            "#d8c5a1",
            "dolomite_rhombs",
            True,
            name_kk="Доломит",
        ),
    )


def _golden_annotations() -> tuple[AnnotationRecord, ...]:
    base = dict(
        anchor=AnnotationAnchor.DEPTH,
        track_id="gas",
        depth=1250.0,
        axis_value=None,
        axis_id=None,
        parameter_mnemonic=None,
        parameter_value=None,
        unit="",
        x_fraction=0.5,
        asset_ref=None,
        visible=True,
        locked=False,
        print_enabled=True,
        scope_id="dataset:golden:default",
    )
    return (
        AnnotationRecord(
            annotation_id="callout-gas",
            kind=AnnotationKind.CALLOUT,
            text="Total gas peak",
            offset_x=18.0,
            offset_y=-46.0,
            width=220.0,
            height=76.0,
            style=AnnotationStyle(),
            **base,
        ),
        AnnotationRecord(
            annotation_id="warning-rotated",
            kind=AnnotationKind.CALLOUT,
            text="Check lag correction",
            offset_x=-238.0,
            offset_y=-40.0,
            width=210.0,
            height=72.0,
            style=AnnotationStyle(
                fill_color="#fff7ed",
                border_color="#ea580c",
                leader_color="#ea580c",
                text_color="#7c2d12",
                rotation=12.0,
                bold=True,
            ),
            **base,
        ),
        AnnotationRecord(
            annotation_id="comment-note",
            kind=AnnotationKind.COMMENT,
            text="Lithology transition",
            offset_x=12.0,
            offset_y=18.0,
            width=190.0,
            height=64.0,
            style=AnnotationStyle(shadow=False, border_color="#64748b"),
            **base,
        ),
        AnnotationRecord(
            annotation_id="value-edge",
            kind=AnnotationKind.VALUE,
            text="C1 = 12.4 %",
            offset_x=28.0,
            offset_y=26.0,
            width=180.0,
            height=58.0,
            style=AnnotationStyle(
                fill_color="#eff6ff",
                border_color="#2563eb",
                leader_color="#2563eb",
            ),
            **base,
        ),
    )


def _render_surface_svg(surface: str) -> str:
    if surface not in {"screen", "print"}:
        raise ValueError(f"unknown golden surface: {surface}")
    grid = _grid_payload()[surface]
    annotation_payload = _annotation_payload()
    annotations = annotation_payload["annotations"]
    legends = _legend_payload()["entries"]["en"]
    patterns = {item["requested_key"]: item for item in _lithotype_payload()["patterns"]}
    if surface == "screen":
        width, height, unit = 900.0, 1400.0, "px"
        plot = LayoutRect(**grid["rect"])
        lithology_rect = LayoutRect(775.0, 80.0, 70.0, 1180.0)
        legend_rect = LayoutRect(60.0, 1280.0, 785.0, 90.0)
    else:
        width, height, unit = 210.0, 297.0, "mm"
        plot = LayoutRect(**grid["rect"])
        lithology_rect = LayoutRect(168.0, 20.0, 18.0, 230.0)
        legend_rect = LayoutRect(15.0, 255.0, 180.0, 30.0)

    lines = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{_num(width)}{unit}" '
        f'height="{_num(height)}{unit}" viewBox="0 0 {_num(width)} {_num(height)}">',
        "<defs>",
    ]
    for key in ("sandstone_bricks", "clay_dash", "dolomite_rhombs"):
        descriptor = resolve_lithology_pattern(key)
        pattern_id = _svg_id(key)
        if descriptor.kind == "bitmap" and descriptor.asset_path is not None:
            payload = b64encode(descriptor.asset_path.read_bytes()).decode("ascii")
            tile_width = descriptor.width_px or 14
            tile_height = descriptor.height_px or 14
            scale = 1.0 if surface == "screen" else PX_TO_MM
            lines.append(
                f'<pattern id="{pattern_id}" patternUnits="userSpaceOnUse" '
                f'width="{_num(tile_width * scale)}" height="{_num(tile_height * scale)}">'
                f'<image href="data:image/bmp;base64,{payload}" width="{_num(tile_width * scale)}" '
                f'height="{_num(tile_height * scale)}"/></pattern>'
            )
        else:
            spacing = 8.0 if surface == "screen" else 2.2
            lines.append(
                f'<pattern id="{pattern_id}" patternUnits="userSpaceOnUse" '
                f'width="{_num(spacing)}" height="{_num(spacing)}">'
                f'<path d="M0,{_num(spacing)} L{_num(spacing)},0" stroke="#64748b" '
                f'stroke-width="{_num(1.0 if surface == "screen" else 0.25)}"/></pattern>'
            )
    lines.extend(
        [
            "</defs>",
            f'<rect x="0" y="0" width="{_num(width)}" height="{_num(height)}" fill="#ffffff"/>',
            f'<rect x="{_num(plot.left)}" y="{_num(plot.top)}" width="{_num(plot.width)}" '
            f'height="{_num(plot.height)}" fill="#f8fafc" stroke="#334155" '
            f'stroke-width="{_num(1.0 if surface == "screen" else 0.25)}"/>',
        ]
    )
    for axis in ("x_lines", "y_lines"):
        vertical = axis == "x_lines"
        for item in grid[axis]:
            position = item["position"]
            major = item["major"]
            stroke = "#64748b" if major else "#cbd5e1"
            stroke_width = (
                (1.0 if major else 0.45)
                if surface == "screen"
                else (0.2 if major else 0.1)
            )
            if vertical:
                x1 = x2 = position
                y1, y2 = plot.top, plot.bottom
            else:
                x1, x2 = plot.left, plot.right
                y1 = y2 = position
            lines.append(
                f'<line x1="{_num(x1)}" y1="{_num(y1)}" x2="{_num(x2)}" y2="{_num(y2)}" '
                f'stroke="{stroke}" stroke-width="{_num(stroke_width)}"/>'
            )

    interval_height = lithology_rect.height / 3.0
    lithotypes = (
        ("sandstone_bricks", "#e7cf8b"),
        ("clay_dash", "#9ca3af"),
        ("dolomite_rhombs", "#d8c5a1"),
    )
    for index, (key, color) in enumerate(lithotypes):
        y = lithology_rect.top + interval_height * index
        lines.append(
            f'<rect x="{_num(lithology_rect.left)}" y="{_num(y)}" '
            f'width="{_num(lithology_rect.width)}" height="{_num(interval_height)}" '
            f'fill="url(#{_svg_id(key)})" stroke="{color}" '
            f'stroke-width="{_num(1.0 if surface == "screen" else 0.25)}"/>'
        )

    for entry in annotations:
        layout = entry[surface]
        anchor = layout["anchor"]
        box = layout["box"]
        endpoint = layout["leader_endpoint"]
        if endpoint is not None:
            lines.append(
                f'<line x1="{_num(anchor["x"])}" y1="{_num(anchor["y"])}" '
                f'x2="{_num(endpoint["x"])}" y2="{_num(endpoint["y"])}" '
                f'stroke="#2563eb" stroke-width="{_num(1.2 if surface == "screen" else 0.32)}"/>'
            )
        fill = "#fff7ed" if entry["annotation_id"] == "warning-rotated" else "#ffffff"
        transform = ""
        if entry["rotation_degrees"]:
            cx = box["left"] + box["width"] / 2.0
            cy = box["top"] + box["height"] / 2.0
            transform = (
                f' transform="rotate({_num(entry["rotation_degrees"])} '
                f'{_num(cx)} {_num(cy)})"'
            )
        lines.append(
            f'<rect x="{_num(box["left"])}" y="{_num(box["top"])}" '
            f'width="{_num(box["width"])}" height="{_num(box["height"])}" '
            f'rx="{_num(6.0 if surface == "screen" else 1.6)}" fill="{fill}" '
            f'stroke="#2563eb" stroke-width="'
            f'{_num(1.2 if surface == "screen" else 0.32)}"{transform}/>'
        )
        font_size = 13.0 if surface == "screen" else 3.0
        lines.append(
            f'<text x="{_num(box["left"] + (8.0 if surface == "screen" else 2.0))}" '
            f'y="{_num(box["top"] + (22.0 if surface == "screen" else 5.0))}" '
            f'font-family="Arial" font-size="{_num(font_size)}" fill="#0f172a"{transform}>'
            f'{escape(entry["text"])}</text>'
        )

    cell_width = legend_rect.width / max(1, len(legends))
    lines.append(
        f'<rect x="{_num(legend_rect.left)}" y="{_num(legend_rect.top)}" '
        f'width="{_num(legend_rect.width)}" height="{_num(legend_rect.height)}" '
        f'fill="#ffffff" stroke="#64748b" stroke-width="'
        f'{_num(1.0 if surface == "screen" else 0.25)}"/>'
    )
    for index, entry in enumerate(legends):
        cell_left = legend_rect.left + index * cell_width
        swatch = 28.0 if surface == "screen" else 7.0
        pattern_key = entry["pattern_key"]
        pattern = patterns.get(pattern_key)
        resolved = pattern["resolved_key"] if pattern else pattern_key
        fill = (
            f"url(#{_svg_id(pattern_key)})"
            if resolved.startswith("constructor:")
            else entry["color"]
        )
        lines.append(
            f'<rect x="{_num(cell_left + 4.0 if surface == "screen" else cell_left + 1.0)}" '
            f'y="{_num(legend_rect.top + 8.0 if surface == "screen" else legend_rect.top + 2.0)}" '
            f'width="{_num(swatch)}" height="'
            f'{_num(legend_rect.height - (16.0 if surface == "screen" else 4.0))}" '
            f'fill="{fill}" stroke="#475569" stroke-width="'
            f'{_num(0.8 if surface == "screen" else 0.2)}"/>'
        )
        text_x = cell_left + swatch + (10.0 if surface == "screen" else 2.5)
        text_y = (
            legend_rect.top
            + legend_rect.height / 2.0
            + (5.0 if surface == "screen" else 1.2)
        )
        text_size = 12.0 if surface == "screen" else 2.8
        lines.append(
            f'<text x="{_num(text_x)}" y="{_num(text_y)}" '
            f'font-family="Arial" font-size="{_num(text_size)}" fill="#0f172a">'
            f'{escape(entry["code"] + " — " + entry["name"])}</text>'
        )
    lines.append("</svg>")
    return "\n".join(lines) + "\n"


def _projected_lines(
    origin: float,
    length: float,
    major: int,
    minor: int,
) -> list[dict[str, Any]]:
    return [
        {"position": position, "major": is_major}
        for position, is_major in project_grid_lines(
            length,
            major,
            minor,
            origin=origin,
        )
    ]


def _annotation_layout_dict(layout: AnnotationLayout, unit: str) -> dict[str, Any]:
    return {
        "unit": unit,
        "anchor": {"x": layout.anchor.x, "y": layout.anchor.y},
        "box": _rect_dict(layout.box),
        "leader_endpoint": (
            None
            if layout.leader_endpoint is None
            else {"x": layout.leader_endpoint.x, "y": layout.leader_endpoint.y}
        ),
    }


def _rect_dict(rect: LayoutRect) -> dict[str, float]:
    return {
        "left": rect.left,
        "top": rect.top,
        "width": rect.width,
        "height": rect.height,
    }


def _normalize(value: Any) -> Any:
    if isinstance(value, float):
        if value == 0.0:
            return 0.0
        return round(value, 6)
    if isinstance(value, Mapping):
        return {str(key): _normalize(item) for key, item in sorted(value.items())}
    if isinstance(value, (list, tuple)):
        return [_normalize(item) for item in value]
    if value is None or isinstance(value, (str, int, bool)):
        return value
    raise TypeError(f"unsupported golden value: {type(value).__name__}")


def _canonical_bytes(value: Any) -> bytes:
    return json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    ).encode("utf-8")


def _json_text(value: Any) -> str:
    return json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        indent=2,
        allow_nan=False,
    ) + "\n"


def _num(value: float) -> str:
    return format(round(float(value), 6), ".6f").rstrip("0").rstrip(".") or "0"


def _svg_id(value: str) -> str:
    return "pattern-" + "".join(character if character.isalnum() else "-" for character in value)
