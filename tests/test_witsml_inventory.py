from __future__ import annotations

from pathlib import Path
import zipfile

import pytest

from geoworkbench.importers.witsml import (
    WitsmlInventoryError,
    WitsmlInventoryLimits,
    inspect_witsml,
)


WITSML_NS = "http://www.energistics.org/energyml/data/witsmlv2"
COMMON_NS = "http://www.energistics.org/energyml/data/commonv2"
CHANNEL_UUID = "0d4d2c32-47a8-4fc9-9f48-42a00a6ebdda"


def _channel_xml(*, uuid: str = CHANNEL_UUID, version: str = "2.1") -> str:
    return f"""<?xml version="1.0" encoding="UTF-8"?>
<Channel xmlns="{WITSML_NS}"
         xmlns:eml="{COMMON_NS}"
         schemaVersion="{version}"
         uuid="{uuid}">
  <eml:Citation>
    <eml:Title>Bit depth</eml:Title>
    <eml:Description>Measured depth channel</eml:Description>
  </eml:Citation>
  <Mnemonic>DEPT</Mnemonic>
  <DataType>double</DataType>
  <Uom>m</Uom>
  <GrowingStatus>active</GrowingStatus>
  <Source>WITS rig feed</Source>
  <TimeDepth>depth</TimeDepth>
  <LoggingMethod>MWD</LoggingMethod>
  <ChannelClass>
    <eml:Title>Depth</eml:Title>
  </ChannelClass>
  <StartIndex>
    <Depth uom="m">1000.0</Depth>
  </StartIndex>
  <EndIndex>
    <Depth uom="m">1250.5</Depth>
  </EndIndex>
  <Index>
    <IndexType>measured depth</IndexType>
    <Uom>m</Uom>
    <Direction>increasing</Direction>
    <Mnemonic>DEPT</Mnemonic>
    <DatumReference>
      <eml:Title>Rotary Kelly Bushing</eml:Title>
    </DatumReference>
  </Index>
  <Wellbore>
    <eml:ContentType>application/x-witsml+xml;version=2.1;type=Wellbore</eml:ContentType>
    <eml:Title>SG-8</eml:Title>
    <eml:Uuid>944d97b8-b5e9-46de-a9a6-3fe0e536857b</eml:Uuid>
  </Wellbore>
</Channel>
"""


def _wellbore_xml(*, uuid: str = "944d97b8-b5e9-46de-a9a6-3fe0e536857b") -> str:
    return f"""<?xml version="1.0" encoding="UTF-8"?>
<Wellbore xmlns="{WITSML_NS}"
          xmlns:eml="{COMMON_NS}"
          schemaVersion="2.1"
          uuid="{uuid}">
  <eml:Citation>
    <eml:Title>SG-8</eml:Title>
  </eml:Citation>
  <GrowingStatus>active</GrowingStatus>
</Wellbore>
"""


def test_inspect_channel_extracts_object_channel_and_reference_metadata(
    tmp_path: Path,
) -> None:
    source = tmp_path / "channel.xml"
    source.write_text(_channel_xml(), encoding="utf-8")

    inventory = inspect_witsml(source)

    assert inventory.schema_versions == ("2.1",)
    assert inventory.type_counts == {"Channel": 1}
    assert len(inventory.channels) == 1

    item = inventory.channels[0]
    assert item.object_type == "Channel"
    assert item.title == "Bit depth"
    assert item.description == "Measured depth channel"
    assert item.growing_status == "active"
    assert item.uuid == CHANNEL_UUID
    assert item.element_count > 10

    channel = item.channel
    assert channel is not None
    assert channel.mnemonic == "DEPT"
    assert channel.data_type == "double"
    assert channel.uom == "m"
    assert channel.source == "WITS rig feed"
    assert channel.time_depth == "depth"
    assert channel.logging_method == "MWD"
    assert channel.channel_class == "Depth"
    assert channel.start_index == "1000.0 m"
    assert channel.end_index == "1250.5 m"
    assert len(channel.indexes) == 1
    assert channel.indexes[0].mnemonic == "DEPT"
    assert channel.indexes[0].datum_reference == "Rotary Kelly Bushing"

    assert len(item.references) == 1
    assert item.references[0].relation == "Wellbore"
    assert item.references[0].title == "SG-8"


def test_inspect_zip_inventory_reads_multiple_objects_without_extracting(
    tmp_path: Path,
) -> None:
    package = tmp_path / "objects.epc"
    with zipfile.ZipFile(package, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        archive.writestr("objects/wellbore.xml", _wellbore_xml())
        archive.writestr("objects/channel.witsml", _channel_xml())
        archive.writestr("metadata/readme.txt", "not XML")

    inventory = inspect_witsml(package)

    assert [item.object_type for item in inventory.objects] == ["Channel", "Wellbore"]
    assert inventory.type_counts == {"Channel": 1, "Wellbore": 1}
    assert not any(path.name == "objects" for path in tmp_path.iterdir())


def test_invalid_member_in_mixed_package_becomes_diagnostic(
    tmp_path: Path,
) -> None:
    package = tmp_path / "mixed.zip"
    with zipfile.ZipFile(package, "w") as archive:
        archive.writestr("good.xml", _wellbore_xml())
        archive.writestr("broken.xml", "<not-closed>")

    inventory = inspect_witsml(package)

    assert len(inventory.objects) == 1
    assert len(inventory.diagnostics) == 1
    assert inventory.diagnostics[0].severity == "error"
    assert inventory.diagnostics[0].source_name == "broken.xml"


def test_directory_inventory_is_recursive_and_reports_duplicate_uuid(
    tmp_path: Path,
) -> None:
    nested = tmp_path / "nested"
    nested.mkdir()
    (tmp_path / "first.xml").write_text(_wellbore_xml(), encoding="utf-8")
    (nested / "second.witsml").write_text(_wellbore_xml(), encoding="utf-8")

    inventory = inspect_witsml(tmp_path)

    assert len(inventory.objects) == 2
    duplicate_warnings = [
        item for item in inventory.diagnostics if "UUID повторяется" in item.message
    ]
    assert len(duplicate_warnings) == 2


@pytest.mark.parametrize(
    ("payload", "message_part"),
    [
        (
            """<Channel xmlns="http://www.witsml.org/schemas/1series"
                        version="1.4.1.1"/>""",
            "не является WITSML 2.x",
        ),
        (
            """<Channel xmlns="http://evil.example/energistics.org/energyml/data/witsmlv2"
                        schemaVersion="2.1"/>""",
            "не является WITSML 2.x",
        ),
        (
            f"""{' ' * 300_000}<!DOCTYPE Channel [<!ENTITY xxe SYSTEM "file:///etc/passwd">]>
<Channel xmlns="{WITSML_NS}" schemaVersion="2.1">&xxe;</Channel>""",
            "небезопасный XML",
        ),
        (
            _channel_xml(version="1.4.1.1"),
            "Неподдерживаемая schemaVersion",
        ),
    ],
    ids=(
        "witsml-1-namespace",
        "lookalike-namespace",
        "padded-doctype",
        "unsupported-version",
    ),
)
def test_rejects_non_witsml2_or_unsafe_xml(
    tmp_path: Path,
    payload: str,
    message_part: str,
) -> None:
    source = tmp_path / "unsafe.xml"
    source.write_text(payload, encoding="utf-8")

    with pytest.raises(WitsmlInventoryError, match=message_part):
        inspect_witsml(source)


def test_rejects_zip_path_traversal(tmp_path: Path) -> None:
    package = tmp_path / "unsafe.zip"
    with zipfile.ZipFile(package, "w") as archive:
        archive.writestr("../outside.xml", _wellbore_xml())

    with pytest.raises(WitsmlInventoryError, match="Небезопасный путь"):
        inspect_witsml(package)


def test_resource_limits_are_enforced(tmp_path: Path) -> None:
    source = tmp_path / "channel.xml"
    source.write_text(_channel_xml(), encoding="utf-8")

    with pytest.raises(WitsmlInventoryError, match="безопасный лимит"):
        inspect_witsml(
            source,
            limits=WitsmlInventoryLimits(max_file_size=32),
        )

    with pytest.raises(ValueError, match="max_files"):
        WitsmlInventoryLimits(max_files=True)
