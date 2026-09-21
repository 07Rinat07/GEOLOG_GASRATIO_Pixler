from __future__ import annotations

from io import BytesIO
from pathlib import Path
import struct
import zipfile

import pytest

from geoworkbench.forms.models import FormAxisKind
from geoworkbench.importers.delphi_stream import DelphiValueType
from geoworkbench.importers.delphi_text_stream import (
    parse_delphi_text_component_stream,
)
from geoworkbench.importers.legacy_geosight_forms import (
    LegacyGeoSightImportError,
    LegacyGeoSightSourceKind,
    detect_geosight_source,
    import_legacy_geosight_file,
)


def _text_desktop() -> bytes:
    return """[Desktop]
Count=2
ActivePage=1
Name0='Бурение'
Name1=#1043#1072#1079
[0]
object TfmGSComplexForm
  Caption = 'Бурение'
  ClientWidth = 900
  ClientHeight = 700
  object Chart1: TGSChart
    Left = 20
    Top = 80
    Width = 420
    Height = 560
    object HookSeries: TGSChartSeries
      GID = 200
      StreamID = 'Time1s'
      Units = #1090
      Pen.Color = clBlue
    end
    object PressureSeries: TGSChartSeries
      GID = 300
      StreamID = 'Time1s'
      Units = #1072#1090#1084
      Pen.Color = clRed
    end
  end
end
[1]
object TfmGSComplexForm
  Caption = #1043#1072#1079
  ClientWidth = 900
  ClientHeight = 700
  object GasChart: TGSChart
    Left = 20
    Top = 80
    Width = 420
    Height = 560
    object MethaneSeries: TGSChartSeries
      GID = 1601
      StreamID = 'Time1s'
      Units = '%'
    end
  end
end
""".encode("cp1251")


def _short(value: str) -> bytes:
    payload = value.encode("cp1251")
    return bytes([len(payload)]) + payload


def _typed_value(value: object) -> bytes:
    if isinstance(value, int):
        if -128 <= value <= 127:
            return bytes([DelphiValueType.INT8]) + struct.pack("<b", value)
        return bytes([DelphiValueType.INT16]) + struct.pack("<h", value)
    if isinstance(value, str):
        return bytes([DelphiValueType.STRING]) + _short(value)
    raise TypeError(value)


def _binary_component(
    class_name: str,
    name: str,
    properties: dict[str, object],
    children: list[bytes] | None = None,
) -> bytes:
    payload = bytearray(_short(class_name) + _short(name))
    for key, value in properties.items():
        payload += _short(key) + _typed_value(value)
    payload += b"\x00"
    for child in children or ():
        payload += child
    payload += b"\x00"
    return bytes(payload)


def _binary_form() -> bytes:
    series = _binary_component(
        "TGSChartSeries",
        "HookSeries",
        {"GID": 200, "StreamID": "Time1s", "Units": "т"},
    )
    chart = _binary_component(
        "TGSChart",
        "Chart1",
        {"Left": 10, "Top": 50, "Width": 400, "Height": 500},
        [series],
    )
    root = _binary_component(
        "TReviewForm",
        "MainForm",
        {"Caption": "Бинарная форма", "Width": 800, "Height": 600},
        [chart],
    )
    return b"legacy-wrapper\x00TPF0" + root


def test_text_parser_reads_desktop_pages_and_pascal_strings() -> None:
    document = parse_delphi_text_component_stream(_text_desktop())

    assert document.encoding == "cp1251"
    assert document.active_page == 1
    assert len(document.components) == 2
    assert document.components[0].properties["Caption"] == "Бурение"
    assert document.components[1].properties["Caption"] == "Газ"
    assert document.page_name(0) == "'Бурение'"
    assert document.page_name(1) == "#1043#1072#1079"


def test_text_parser_reads_geosight_collection_with_compact_end_marker() -> None:
    payload = """object SensGrid1: TSensGrid
  Sensors = <
    item
      GID = 300
      Name = #1044#1072#1074#1083#1077#1085#1080#1077
      StreamID = 'Time1s'
      Units = #1072#1090#1084
    end>
end
""".encode("cp1251")

    document = parse_delphi_text_component_stream(payload)
    sensors = document.components[0].properties["Sensors"]

    assert isinstance(sensors, list)
    assert sensors[0]["GID"] == 300
    assert sensors[0]["Name"] == "Давление"
    assert sensors[0]["StreamID"] == "Time1s"
    assert sensors[0]["Units"] == "атм"


@pytest.mark.parametrize(
    ("payload", "expected"),
    [
        (_text_desktop(), LegacyGeoSightSourceKind.TEXT_FORM),
        (_binary_form(), LegacyGeoSightSourceKind.BINARY_FORM),
        (
            b"[Form]\r\nStyle=2\r\nClass=TReviewForm\r\nService=GeoScape\r\n",
            LegacyGeoSightSourceKind.GSF_DESCRIPTOR,
        ),
        (b"not-a-form", LegacyGeoSightSourceKind.UNKNOWN),
    ],
)
def test_source_detection_is_content_based(
    payload: bytes,
    expected: LegacyGeoSightSourceKind,
) -> None:
    assert detect_geosight_source(payload) is expected


def test_zip_payload_is_reserved_for_gs2_data_import() -> None:
    buffer = BytesIO()
    with zipfile.ZipFile(buffer, "w") as archive:
        archive.writestr("GS2.mdb", b"metadata")
        archive.writestr("GS2#1.db", b"table")

    payload = buffer.getvalue()
    assert detect_geosight_source(payload) is LegacyGeoSightSourceKind.GS2_CONTAINER


def test_desktop_import_maps_legacy_gid_to_canonical_sensors_and_active_page(
    tmp_path: Path,
) -> None:
    source = tmp_path / "unit9.gs2"
    source.write_bytes(_text_desktop())

    bundle = import_legacy_geosight_file(source)

    assert bundle.source_kind is LegacyGeoSightSourceKind.TEXT_FORM
    assert len(bundle.results) == 2
    assert bundle.active_index == 1
    assert bundle.active_result.form.name == "Газ"

    drilling = bundle.results[0].form
    assert drilling.axis_kind is FormAxisKind.TIME
    drilling_bindings = [
        binding
        for column in drilling.columns
        for track in column.tracks
        for binding in track.bindings
    ]
    by_canonical = {item.canonical_parameter_id: item for item in drilling_bindings}
    assert "HKLD" in by_canonical
    assert "SPP" in by_canonical
    assert by_canonical["HKLD"].source_mnemonic == "HKLD"
    assert by_canonical["HKLD"].unit == "т"
    assert by_canonical["SPP"].source_mnemonic == "SPP"
    assert by_canonical["SPP"].unit == "атм"

    gas_bindings = [
        binding
        for column in bundle.results[1].form.columns
        for track in column.tracks
        for binding in track.bindings
    ]
    assert {item.canonical_parameter_id for item in gas_bindings} >= {"C1"}


def test_binary_form_reuses_same_gid_mapping_pipeline(tmp_path: Path) -> None:
    source = tmp_path / "form.grc"
    source.write_bytes(_binary_form())

    bundle = import_legacy_geosight_file(source)

    assert bundle.source_kind is LegacyGeoSightSourceKind.BINARY_FORM
    result = bundle.active_result
    assert result.form.axis_kind is FormAxisKind.TIME
    bindings = [
        binding
        for column in result.form.columns
        for track in column.tracks
        for binding in track.bindings
    ]
    assert any(
        item.canonical_parameter_id == "HKLD" and item.source_mnemonic == "HKLD"
        for item in bindings
    )
    assert result.header_template.properties["source_format"] == "geosight-delphi-binary"


def test_gsf_descriptor_resolves_numbered_form_grc_companion(tmp_path: Path) -> None:
    descriptor = tmp_path / "Forms 2018(1).gsf"
    descriptor.write_text(
        "[Form]\nStyle=2\nClass=TReviewForm\nService=GeoScape\n",
        encoding="cp1251",
    )
    companion = tmp_path / "Forms 2018Form(1).grc"
    companion.write_bytes(_binary_form())

    bundle = import_legacy_geosight_file(descriptor)

    assert bundle.source_kind is LegacyGeoSightSourceKind.GSF_DESCRIPTOR
    assert bundle.companion_source == companion
    assert bundle.active_result.header_template.properties["source_format"] == "geosight-gsf-grc"


def test_form_import_rejects_real_gs2_zip_container(tmp_path: Path) -> None:
    source = tmp_path / "data.gs2"
    with zipfile.ZipFile(source, "w") as archive:
        archive.writestr("GS2.mdb", b"metadata")
        archive.writestr("GS2#1.db", b"table")

    with pytest.raises(LegacyGeoSightImportError, match="импорт GS2"):
        import_legacy_geosight_file(source)
