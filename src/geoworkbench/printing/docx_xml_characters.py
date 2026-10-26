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



def docx_word_text_parts(value: object) -> tuple[tuple[str, str], ...]:
    """Preserve hard line breaks and tabs as Word run elements, not XML whitespace.

    Return ordered ("text", value), ("break", ""), ("tab", "") pairs.
    Never change the incoming report/source object.
    """
    safe = docx_xml_safe_text(value).replace("\r\n", "\n").replace("\r", "\n")
    parts: list[tuple[str, str]] = []
    start = 0
    for position, character in enumerate(safe):
        if character not in "\n\t":
            continue
        if position > start:
            parts.append(("text", safe[start:position]))
        parts.append(("break" if character == "\n" else "tab", ""))
        start = position + 1
    if start < len(safe):
        parts.append(("text", safe[start:]))
    if not parts:
        parts.append(("text", ""))
    return tuple(parts)
