from __future__ import annotations

import struct

from geoworkbench.importers.delphi_stream import (
    DelphiStreamError,
    DelphiValueType,
    parse_delphi_component_stream,
)

import pytest


def _short(value: str) -> bytes:
    payload = value.encode("cp1251")
    return bytes([len(payload)]) + payload


def _value(value: object) -> bytes:
    if isinstance(value, bool):
        return bytes([DelphiValueType.TRUE if value else DelphiValueType.FALSE])
    if isinstance(value, int):
        return bytes([DelphiValueType.INT16]) + struct.pack("<h", value)
    if isinstance(value, str):
        return bytes([DelphiValueType.STRING]) + _short(value)
    raise TypeError(value)


def _component(
    class_name: str,
    name: str,
    properties: dict[str, object],
    children: list[bytes] | None = None,
) -> bytes:
    payload = bytearray(_short(class_name) + _short(name))
    for key, value in properties.items():
        payload += _short(key) + _value(value)
    payload += b"\x00"
    for child in children or []:
        payload += child
    payload += b"\x00"
    return bytes(payload)


def test_binary_delphi_stream_is_decoded_without_instantiating_components() -> None:
    child = _component(
        "TLabel",
        "TitleLabel",
        {"Caption": "Глубинка", "Left": 10, "Top": 5},
    )
    root = _component(
        "TForm",
        "MainForm",
        {"Caption": "SKF форма", "Width": 1200},
        [child],
    )
    parsed = parse_delphi_component_stream(b"SKF-WRAPPER\x00TPF0" + root)
    assert parsed.signature_offset == 12
    assert parsed.root.class_name == "TForm"
    assert parsed.root.properties["Caption"] == "SKF форма"
    assert parsed.root.children[0].properties["Caption"] == "Глубинка"


def test_missing_signature_is_rejected() -> None:
    with pytest.raises(DelphiStreamError, match="TPF0"):
        parse_delphi_component_stream(b"not-a-delphi-stream")
