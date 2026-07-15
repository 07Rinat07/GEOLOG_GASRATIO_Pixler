import pytest

from geoworkbench.data.lossless_las import (
    LasSectionEditError,
    NewlineStyle,
    parse_lossless_las,
    replace_section_roles,
)


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


def test_replace_section_roles_preserves_preamble_unknown_sections_and_order() -> None:
    raw = (
        b"# preamble\r\n"
        b"~V\r\nVERS. 1.2\r\n"
        b"~Other Vendor Data\r\n# exact comment\r\nVALUE. 42\r\n"
        b"~A\r\n100 1\r\n"
    )
    document = parse_lossless_las(raw)

    changed = replace_section_roles(
        document,
        {
            "version": b"~Version\r\nVERS. 2.0\r\n",
            "ascii": b"~ASCII\r\n100 9\r\n",
        },
    )

    assert changed.preamble == b"# preamble\r\n"
    assert b"~Other Vendor Data\r\n# exact comment\r\nVALUE. 42\r\n" in changed.to_bytes()
    assert [section.name for section in changed.sections] == ["version", "other", "ascii"]
    assert changed.to_bytes().endswith(b"~ASCII\r\n100 9\r\n")


def test_replace_section_roles_rejects_wrong_or_ambiguous_section() -> None:
    duplicate = parse_lossless_las(b"~W\nA. 1\n~Well\nB. 2\n~A\n1\n")

    with pytest.raises(LasSectionEditError, match="неоднозначная"):
        replace_section_roles(duplicate, {"well": b"~Well\nWELL. TEST\n"})
    with pytest.raises(LasSectionEditError, match="не может заменить"):
        replace_section_roles(duplicate, {"ascii": b"~Curve\nDEPT.M\n"})


def test_replace_section_requires_line_boundary_before_following_section() -> None:
    document = parse_lossless_las(b"~V\nVERS. 1.2\n~A\n1\n")

    with pytest.raises(LasSectionEditError, match="переводом строки"):
        replace_section_roles(document, {"version": b"~V\nVERS. 2.0"})


def test_utf8_bom_is_preserved_as_preamble_when_section_is_replaced() -> None:
    document = parse_lossless_las(b"\xef\xbb\xbf~V\r\nVERS. 1.2\r\n~A\r\n1\r\n")

    changed = replace_section_roles(document, {"version": b"~V\r\nVERS. 2.0\r\n"})

    assert document.preamble == b"\xef\xbb\xbf"
    assert changed.to_bytes().startswith(b"\xef\xbb\xbf~V")
    assert changed.to_bytes().count(b"\xef\xbb\xbf") == 1
