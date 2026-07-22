from __future__ import annotations

from pathlib import Path
import struct

from geoworkbench.forms.models import FormAxisKind
from geoworkbench.importers.delphi_stream import DelphiValueType, parse_delphi_component_stream
from geoworkbench.importers.skf_importer import import_skf_payload
from geoworkbench.tablet.models import TrackKind


def _short(value: str) -> bytes:
    payload = value.encode("cp1251")
    assert len(payload) < 256
    return bytes([len(payload)]) + payload


def _value(value: object) -> bytes:
    if isinstance(value, bool):
        return bytes([DelphiValueType.TRUE if value else DelphiValueType.FALSE])
    if isinstance(value, int):
        if -128 <= value <= 127:
            return bytes([DelphiValueType.INT8]) + struct.pack("<b", value)
        if -32768 <= value <= 32767:
            return bytes([DelphiValueType.INT16]) + struct.pack("<h", value)
        return bytes([DelphiValueType.INT32]) + struct.pack("<i", value)
    if isinstance(value, float):
        return bytes([DelphiValueType.DOUBLE]) + struct.pack("<d", value)
    if isinstance(value, str):
        return bytes([DelphiValueType.STRING]) + _short(value)
    raise TypeError(value)


def _component(
    class_name: str,
    name: str,
    properties: dict[str, object],
    children: list[bytes] | None = None,
) -> bytes:
    payload = bytearray()
    payload += _short(class_name)
    payload += _short(name)
    for key, value in properties.items():
        payload += _short(key)
        payload += _value(value)
    payload += b"\x00"
    for child in children or []:
        payload += child
    payload += b"\x00"
    return bytes(payload)


def _sample_stream() -> bytes:
    title = _component(
        "TLabel",
        "lblTitle",
        {"Left": 20, "Top": 10, "Width": 600, "Height": 30, "Caption": "МАСТЕРЛОГ"},
    )
    depth = _component(
        "TTrackPanel",
        "DepthColumn",
        {
            "Left": 0,
            "Top": 160,
            "Width": 100,
            "Height": 700,
            "Caption": "Глубина",
        },
    )
    curve = _component(
        "TCurveSeries",
        "ROPSeries",
        {
            "Mnemonic": "ROP",
            "Caption": "Скорость проходки",
            "Unit": "м/ч",
            "XMin": 0.0,
            "XMax": 100.0,
            "LineColor": "clRed",
        },
    )
    drilling = _component(
        "TTrackPanel",
        "DrillingColumn",
        {
            "Left": 100,
            "Top": 160,
            "Width": 300,
            "Height": 700,
            "Caption": "Параметры бурения",
            "GridX": True,
        },
        [curve],
    )
    gas_curve = _component(
        "TCurveSeries",
        "C1Series",
        {"Mnemonic": "C1", "Caption": "Метан C1", "Unit": "%", "XMin": 0.001, "XMax": 100.0},
    )
    gas = _component(
        "TGasTrack",
        "GasColumn",
        {"Left": 400, "Top": 160, "Width": 260, "Height": 700, "Caption": "Газ"},
        [gas_curve],
    )
    root = _component(
        "TMasterlogForm",
        "MainForm",
        {"Caption": "Глубинка SKF", "Left": 0, "Top": 0, "Width": 1200, "Height": 900},
        [title, depth, drilling, gas],
    )
    return b"SKF-WRAPPER\x00" + b"TPF0" + root


def test_delphi_component_reader_accepts_signature_inside_wrapper() -> None:
    parsed = parse_delphi_component_stream(_sample_stream())
    assert parsed.signature_offset == 12
    assert parsed.root.class_name == "TMasterlogForm"
    assert parsed.root.name == "MainForm"
    assert len(parsed.root.children) == 4


def test_skf_importer_builds_form_and_masterlog_header() -> None:
    result = import_skf_payload(_sample_stream(), source_name="Глубинка.skf")
    assert result.form.axis_kind is FormAxisKind.DEPTH
    assert result.form.name == "Глубинка SKF"
    assert len(result.form.columns) == 3
    assert result.form.print_header_template_id == result.header_template.template_id
    assert result.header_template.header_elements
    assert result.header_template.columns
    drilling = next(column for column in result.form.columns if column.title == "Параметры бурения")
    assert drilling.tracks[0].kind is TrackKind.CURVE
    assert drilling.tracks[0].bindings[0].source_mnemonic == "ROP"
    assert drilling.tracks[0].bindings[0].x_min == 0.0
    assert drilling.tracks[0].bindings[0].x_max == 100.0
    gas = next(column for column in result.form.columns if column.title == "Газ")
    assert gas.tracks[0].kind is TrackKind.GAS
    assert gas.tracks[0].bindings[0].source_mnemonic == "C1"
    assert result.report.component_count == 7
    assert result.report.source_size_bytes == len(_sample_stream())
    assert len(result.report.source_sha256) == 64
    assert result.report.column_count == 3


def test_imported_form_is_user_editable_and_source_is_traced(tmp_path: Path) -> None:
    path = tmp_path / "example.skf"
    path.write_bytes(_sample_stream())
    result = import_skf_payload(path.read_bytes(), source_name=path.name)
    assert result.form.read_only is False
    assert result.header_template.properties["source_file"] == "example.skf"
    assert result.header_template.properties["source_format"] == "skf-delphi-component-stream"
