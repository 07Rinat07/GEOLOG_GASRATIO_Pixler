#!/usr/bin/env python3
"""Inspect or convert a legacy Delphi SKF component stream.

Inspection uses only the safe neutral Delphi reader. Full conversion requires the
normal application dependencies because it creates FormDocument/MasterlogTemplate
objects and normalises embedded images through Qt.
"""
from __future__ import annotations

import argparse
from dataclasses import asdict
import json
from pathlib import Path
import sys
from typing import Any

from geoworkbench.importers.delphi_stream import (
    DelphiBinary,
    DelphiComponent,
    DelphiSet,
    parse_delphi_component_stream,
)


def _json_value(value: Any) -> Any:
    if isinstance(value, DelphiBinary):
        return {"type": "binary", "size": len(value.payload)}
    if isinstance(value, DelphiSet):
        return list(value.values)
    if isinstance(value, list):
        return [_json_value(item) for item in value]
    if isinstance(value, dict):
        return {str(key): _json_value(item) for key, item in value.items()}
    if isinstance(value, (str, int, float, bool)) or value is None:
        return value
    return repr(value)


def _component_dict(component: DelphiComponent) -> dict[str, Any]:
    return {
        "class_name": component.class_name,
        "name": component.name,
        "inherited": component.inherited,
        "inline": component.inline,
        "child_position": component.child_position,
        "properties": {key: _json_value(value) for key, value in component.properties.items()},
        "children": [_component_dict(child) for child in component.children],
    }


def _print_tree(component: DelphiComponent, depth: int = 0) -> None:
    indent = "  " * depth
    caption = next(
        (
            value
            for key, value in component.properties.items()
            if key.casefold() in {"caption", "title", "text"} and isinstance(value, str)
        ),
        "",
    )
    suffix = f" — {caption}" if caption else ""
    print(f"{indent}{component.class_name} {component.name}{suffix}")
    for child in component.children:
        _print_tree(child, depth + 1)


def _convert(source: Path, output: Path) -> None:
    try:
        from geoworkbench.forms.codec import form_to_dict
        from geoworkbench.importers.skf_importer import import_skf_file
    except ImportError as exc:
        raise SystemExit(
            "Full conversion requires the installed application dependencies "
            "(including PySide6). Run this command from the project virtual environment."
        ) from exc

    result = import_skf_file(source)
    output.mkdir(parents=True, exist_ok=True)
    stem = source.stem
    (output / f"{stem}.form.json").write_text(
        json.dumps(form_to_dict(result.form), ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    (output / f"{stem}.masterlog.json").write_text(
        json.dumps(asdict(result.header_template), ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    assets = output / f"{stem}_assets"
    for asset in result.image_assets.values():
        assets.mkdir(parents=True, exist_ok=True)
        (assets / asset.name).write_bytes(asset.payload)
    (output / f"{stem}.report.json").write_text(
        json.dumps(asdict(result.report), ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    print(f"Converted form: {output / f'{stem}.form.json'}")
    print(f"Converted header: {output / f'{stem}.masterlog.json'}")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("source", type=Path, help="Path to the .skf file")
    parser.add_argument("--encoding", help="Force legacy string encoding, e.g. cp1251 or cp866")
    parser.add_argument("--dump-json", type=Path, help="Write the neutral Delphi component tree")
    parser.add_argument("--convert-dir", type=Path, help="Write converted form/header JSON files")
    args = parser.parse_args()

    payload = args.source.read_bytes()
    stream = parse_delphi_component_stream(payload, encoding=args.encoding)
    print(f"Source: {args.source}")
    print(f"TPF0 offset: {stream.signature_offset}")
    print(f"Root: {stream.root.class_name} {stream.root.name}")
    print(f"Components: {len(stream.root.walk())}")
    _print_tree(stream.root)
    if args.dump_json:
        args.dump_json.parent.mkdir(parents=True, exist_ok=True)
        args.dump_json.write_text(
            json.dumps(_component_dict(stream.root), ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        print(f"Neutral tree: {args.dump_json}")
    if args.convert_dir:
        _convert(args.source, args.convert_dir)
    return 0


if __name__ == "__main__":
    sys.exit(main())
