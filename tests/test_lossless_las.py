from geoworkbench.data.lossless_las import NewlineStyle, parse_lossless_las


def test_lossless_document_preserves_exact_bytes_and_section_order() -> None:
    raw = (
        b"# preamble\r\n"
        b"~Version Information\r\n VERS. 2.0\r\n"
        b"~Well Information\r\n WELL. TEST\r\n"
        b"~Curve Information\r\n DEPT.M\r\n"
        b"~Ascii Log Data\r\n100 1\r\n"
    )

    document = parse_lossless_las(raw)

    assert document.to_bytes() == raw
    assert document.preamble == b"# preamble\r\n"
    assert document.newline_style is NewlineStyle.CRLF
    assert document.encoding == "utf-8"
    assert [section.name for section in document.sections] == [
        "version",
        "well",
        "curve",
        "ascii",
    ]
    assert document.section_bytes(document.sections[-1]) == b"~Ascii Log Data\r\n100 1\r\n"


def test_lossless_document_detects_bom_encoding_and_mixed_newlines() -> None:
    raw = b"\xef\xbb\xbf~V\r\nVERS. 2.0\n~A\r\n1 2\r\n"

    document = parse_lossless_las(raw)

    assert document.encoding == "utf-8-sig"
    assert document.newline_style is NewlineStyle.MIXED
    assert [section.name for section in document.sections] == ["v", "a"]
    assert document.to_bytes() == raw


def test_lossless_document_detects_cp1251_without_changing_content() -> None:
    raw = "~Other\n# Примечание\n".encode("cp1251")

    document = parse_lossless_las(raw)

    assert document.encoding == "cp1251"
    assert document.sections[0].header == "Other"
    assert document.to_bytes() == raw


def test_lossless_document_without_sections_keeps_preamble() -> None:
    raw = b"not a LAS document\n"

    document = parse_lossless_las(raw)

    assert document.sections == ()
    assert document.preamble == raw
    assert document.to_bytes() == raw
