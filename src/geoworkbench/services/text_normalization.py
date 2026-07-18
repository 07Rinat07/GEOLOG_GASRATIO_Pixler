from __future__ import annotations

import re
import unicodedata

_CONTROL = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]")
_SPACES = re.compile(r"[ \t\u00a0]+")
_MOJIBAKE = set("ÃÂÐÑРСЃРµРЅР°Р»РёРєРÄÅÆÇÈÉÊËÌÍÎÏÐÑÒÓÔÕÖ×ØÙÚÛÜÝÞß")


def clean_display_text(value: object, *, fallback: str = "") -> str:
    """Return readable Unicode and repair common LAS mojibake.

    Handles the two most frequent legacy failures:
    * Windows-1251 bytes decoded as Latin-1 (``ÄÈÀ...``);
    * UTF-8 bytes decoded as Windows-1251/Latin-1 (``Рџ...`` / ``Ð...``).
    """

    text = "" if value is None else str(value)
    text = unicodedata.normalize("NFC", _CONTROL.sub("", text)).replace("\ufffd", "")
    candidates = {text}
    for source, target in (
        ("latin-1", "cp1251"),
        ("cp1251", "utf-8"),
        ("latin-1", "utf-8"),
    ):
        try:
            candidates.add(text.encode(source).decode(target))
        except (UnicodeEncodeError, UnicodeDecodeError):
            pass
    best = max(candidates, key=_readability_score)
    best = _SPACES.sub(" ", best).strip()
    return best or fallback


def clean_mnemonic(value: object, *, fallback: str = "CURVE") -> str:
    text = clean_display_text(value, fallback=fallback)
    # LAS mnemonic must stay single-line; spaces are made deterministic.
    text = "_".join(text.split())
    return text or fallback


def _readability_score(text: str) -> tuple[int, int, int, int]:
    printable = sum(ch.isprintable() and ch not in "\ufffd" for ch in text)
    letters = sum(ch.isalpha() or ch.isdigit() for ch in text)
    cyrillic = sum("А" <= ch <= "я" or ch in "Ёё" for ch in text)
    suspicious = sum(ch in _MOJIBAKE for ch in text)
    controls = sum(unicodedata.category(ch).startswith("C") for ch in text)
    # Prefer readable letters and valid Cyrillic, heavily penalize classic mojibake.
    return (letters + cyrillic * 2 - suspicious * 5 - controls * 10, printable, -suspicious, -len(text))
