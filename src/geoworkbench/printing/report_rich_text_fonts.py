from __future__ import annotations

from PySide6.QtGui import QTextCursor, QTextDocument, QTextFormat


def apply_explicit_rich_text_font_sizes(document: QTextDocument) -> None:
    """Make explicit CSS point sizes win over Qt's relative heading adjustments.

    Preserve the rest of each character format, including links and scientific
    superscripts/subscripts. Documents without explicit sizes retain Qt defaults.
    """
    # Qt retains heading-relative size adjustments alongside explicit CSS sizes.
    # The relative adjustment wins during layout unless it is removed. Preserve
    # every other character property (bold, colour, links and inline formatting).
    block = document.begin()
    while block.isValid():
        iterator = block.begin()
        while not iterator.atEnd():
            text_fragment = iterator.fragment()
            char_format = text_fragment.charFormat()
            if char_format.fontPointSize() > 0 and char_format.hasProperty(
                QTextFormat.Property.FontSizeAdjustment,
            ):
                char_format.clearProperty(QTextFormat.Property.FontSizeAdjustment)
                cursor = QTextCursor(document)
                cursor.setPosition(text_fragment.position())
                cursor.setPosition(text_fragment.position() + text_fragment.length(), QTextCursor.MoveMode.KeepAnchor)
                cursor.setCharFormat(char_format)
            iterator += 1
        block = block.next()
