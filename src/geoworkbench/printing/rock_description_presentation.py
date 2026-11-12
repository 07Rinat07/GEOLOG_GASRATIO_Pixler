"""Uniform rock-description presentation; never rewrite stored geology."""

from __future__ import annotations

from html import escape
import re

from PySide6.QtGui import QFont, QTextDocument

from geoworkbench.printing.unicode_support import print_font


ROCK_DESCRIPTION_POINT_SIZE = 9.0
ROCK_DESCRIPTION_COLOR = "#202020"
# Legacy rich-text editor output contains these tags. Do not treat a plain
# geological comparison such as "<5% ... >2%" as HTML.
_RICH_TEXT = re.compile(
    r"<\s*/?\s*(?:html|head|body|p|div|span|br|b|strong|i|em|u|font|"
    r"table|tr|td|ul|ol|li|img|h[1-6]|sup|sub|pre|a)(?=[\s/>])",
    re.IGNORECASE,
)


def rock_description_plain_text(value: str | None) -> str:
    """Extract readable text for display, keeping stored source untouched."""
    text = (value or "").replace("\r\n", "\n").replace("\r", "\n")
    if _RICH_TEXT.search(text):
        document = QTextDocument()
        document.setHtml(text)
        text = document.toPlainText()
    # Object placeholders from embedded images are not geological characters.
    # The original rich record (including images) remains in the editor.
    return text.replace("\ufffc", "").strip()


def rock_description_font(text: str) -> QFont:
    font = print_font(ROCK_DESCRIPTION_POINT_SIZE, text=text)
    font.setWeight(QFont.Weight.Normal)
    font.setItalic(False)
    font.setUnderline(False)
    font.setStrikeOut(False)
    return font


def rock_description_tooltip(top: float, bottom: float, text: str) -> str:
    """Escape all source text so a tooltip cannot interpret it as markup."""
    body = escape(text).replace("\n", "<br/>")
    return f"<div>{top:g}–{bottom:g} m<br/>{body}</div>"
