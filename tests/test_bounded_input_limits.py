from __future__ import annotations

from io import BytesIO
from pathlib import Path

import pytest

from geoworkbench.data.lossless_las import read_lossless_las
from geoworkbench.services.bounded_input import (
    BinaryInputLimits,
    BoundedXmlError,
    InputLimitError,
    XmlInputLimits,
    parse_bounded_xml_bytes,
    parse_bounded_xml_stream,
    read_bounded_binary,
)


class _RecordingStream(BytesIO):
    def __init__(self, payload: bytes) -> None:
        super().__init__(payload)
        self.requested_sizes: list[int] = []

    def read(self, size: int = -1) -> bytes:
        self.requested_sizes.append(size)
        return super().read(size)


def _xml_limits(**changes: int) -> XmlInputLimits:
    values = {
        "max_bytes": 4096,
        "max_depth": 8,
        "max_elements": 32,
        "max_text_bytes": 256,
        "max_attributes": 32,
        "max_attribute_bytes": 512,
        "max_attributes_per_element": 8,
        "chunk_size": 7,
    }
    values.update(changes)
    return XmlInputLimits(**values)


def test_bounded_binary_reader_stops_at_first_byte_over_limit() -> None:
    stream = _RecordingStream(b"x" * 1000)

    with pytest.raises(InputLimitError, match="bytes limit exceeded") as error:
        read_bounded_binary(
            stream,
            limits=BinaryInputLimits(max_bytes=31, chunk_size=8),
            source_name="sample.las",
        )

    assert error.value.actual == 32
    assert stream.tell() == 32
    assert max(stream.requested_sizes) <= 8


def test_bounded_xml_stream_preserves_namespace_text_and_tail() -> None:
    payload = b'<Root xmlns="urn:test" a="1">before<Child>value</Child>after</Root>'
    stream = _RecordingStream(payload)

    root = parse_bounded_xml_stream(
        stream,
        limits=_xml_limits(),
        source_name="sample.xml",
    )

    assert root.tag == "{urn:test}Root"
    assert root.attrib == {"a": "1"}
    assert root.text == "before"
    assert root[0].tag == "{urn:test}Child"
    assert root[0].text == "value"
    assert root[0].tail == "after"
    assert max(stream.requested_sizes) <= 7


@pytest.mark.parametrize(
    ("payload", "limit_changes", "limit_name"),
    [
        (b"<a><b><c/></b></a>", {"max_depth": 2}, "XML depth"),
        (b"<a><b/><c/></a>", {"max_elements": 2}, "XML elements"),
        (b"<a>123456</a>", {"max_text_bytes": 5}, "XML text bytes"),
        (b'<a x="1" y="2"/>', {"max_attributes": 1}, "XML attributes"),
        (
            b'<a x="1" y="2"/>',
            {"max_attributes_per_element": 1},
            "attributes per element",
        ),
        (b'<a long="123456"/>', {"max_attribute_bytes": 8}, "attribute bytes"),
    ],
)
def test_bounded_xml_rejects_each_resource_dimension(
    payload: bytes,
    limit_changes: dict[str, int],
    limit_name: str,
) -> None:
    with pytest.raises(InputLimitError, match=limit_name):
        parse_bounded_xml_bytes(
            payload,
            limits=_xml_limits(**limit_changes),
            source_name="limited.xml",
        )


def test_bounded_xml_rejects_late_doctype_without_prefix_scanning() -> None:
    payload = b" " * 1024 + b'<!DOCTYPE a [<!ENTITY x "boom">]><a>&x;</a>'

    with pytest.raises(BoundedXmlError, match="DTD, entity and notation"):
        parse_bounded_xml_bytes(
            payload,
            limits=_xml_limits(max_bytes=4096, max_text_bytes=2048),
            source_name="unsafe.xml",
        )


def test_lossless_las_reader_enforces_size_before_full_read(tmp_path: Path) -> None:
    source = tmp_path / "large.las"
    source.write_bytes(b"~V\nVERS. 2.0\n~A\n" + b"1 2\n" * 100)

    with pytest.raises(InputLimitError, match="bytes limit exceeded"):
        read_lossless_las(source, max_bytes=32, chunk_size=8)


def test_witsml_inventory_applies_depth_and_attribute_limits(tmp_path: Path) -> None:
    from geoworkbench.importers.witsml.inventory import (
        WitsmlInventoryError,
        WitsmlInventoryLimits,
        inspect_witsml,
    )

    source = tmp_path / "deep.xml"
    source.write_text(
        '<Channel xmlns="http://www.energistics.org/energyml/data/witsmlv2" '
        'schemaVersion="2.1" uuid="abc"><A><B><C/></B></A></Channel>',
        encoding="utf-8",
    )

    with pytest.raises(WitsmlInventoryError, match="XML depth"):
        inspect_witsml(source, limits=WitsmlInventoryLimits(max_depth=3))

    with pytest.raises(WitsmlInventoryError, match="attributes per element"):
        inspect_witsml(
            source,
            limits=WitsmlInventoryLimits(max_attributes_per_element=1),
        )


def test_witsml_channel_data_applies_text_limit_during_parse(tmp_path: Path) -> None:
    from geoworkbench.importers.witsml.data_arrays import (
        WitsmlDataError,
        WitsmlDataLimits,
        read_witsml_channel_sets,
    )

    source = tmp_path / "text-heavy.xml"
    source.write_text(
        '<ChannelSet xmlns="http://www.energistics.org/energyml/data/witsmlv2" '
        'schemaVersion="2.1"><Citation><Title>'
        + ("x" * 128)
        + "</Title></Citation></ChannelSet>",
        encoding="utf-8",
    )

    with pytest.raises(WitsmlDataError, match="XML text bytes"):
        read_witsml_channel_sets(
            source,
            limits=WitsmlDataLimits(max_text_bytes=64),
        )


def test_all_witsml_xml_boundaries_use_the_streaming_parser() -> None:
    root = Path(__file__).resolve().parents[1]
    paths = (
        root / "src/geoworkbench/importers/witsml/inventory.py",
        root / "src/geoworkbench/importers/witsml/data_arrays.py",
        root / "src/geoworkbench/importers/witsml1411/parser.py",
        root / "src/geoworkbench/importers/witsml1411/soap.py",
    )

    for path in paths:
        text = path.read_text(encoding="utf-8")
        assert "parse_bounded_xml_" in text, path
        assert "safe_xml_fromstring" not in text, path
