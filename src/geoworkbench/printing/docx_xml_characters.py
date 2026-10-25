"""Keep user-supplied Word text inside the XML 1.0 character repertoire."""

from __future__ import annotations


def docx_xml_safe_text(value: object) -> str:
    """Remove characters disallowed by XML 1.0 without changing the source."""
    return "".join(
        char
        for char in str(value)
        if (
            char in "\t\n\r"
            or 0x20 <= ord(char) <= 0xD7FF
            or 0xE000 <= ord(char) <= 0xFFFD
            or 0x10000 <= ord(char) <= 0x10FFFF
        )
    )
