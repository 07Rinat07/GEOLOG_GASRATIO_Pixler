from __future__ import annotations

import re
import unicodedata

_CONTROL = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]")
_SPACES = re.compile(r"[ \t\u00a0]+")
_WORD = re.compile(r"[A-Za-zА-Яа-яЁёӘәҒғҚқҢңӨөҰұҮүҺһІі]{3,}")

# Normal Russian and Kazakh Cyrillic used by the application UI and LAS metadata.
_ALLOWED_CYRILLIC = set(
    "АБВГДЕЁЖЗИЙКЛМНОПРСТУФХЦЧШЩЪЫЬЭЮЯ"
    "абвгдеёжзийклмнопрстуфхцчшщъыьэюя"
    "ӘәҒғҚқҢңӨөҰұҮүҺһІі"
)

# Characters that occur very frequently when DOS/Windows/UTF-8 text was decoded
# with the wrong codec. They are legitimate Unicode, but are extremely uncommon in
# Russian/Kazakh LAS descriptions and therefore useful as a repair signal.
_SUSPICIOUS = set(
    "ÃÂÐÑØÙÚÛÜÝÞß"
    "‚ƒ„…†‡ˆ‰Š‹ŒŽ‘’“”•–—˜™š›œžŸ"
    "ЄІЇЈЉЊЋЌЎЏђѓєѕіїјљњћќўџҐґ"
    "«»®¬¦¤§¨©±µ¶·¸¹º¼½¾"
)

# (codec used by the broken string, codec of the original bytes).
_REPAIR_PATHS: tuple[tuple[str, str], ...] = (
    ("cp1251", "cp866"),
    ("latin-1", "cp866"),
    ("cp1252", "cp866"),
    ("latin-1", "cp1251"),
    ("cp1252", "cp1251"),
    ("cp1251", "utf-8"),
    ("latin-1", "utf-8"),
    ("cp1252", "utf-8"),
)


def clean_display_text(value: object, *, fallback: str = "") -> str:
    """Return readable Unicode and repair common LAS mojibake.

    Supported failures include UTF-8 decoded as Windows-1251/Latin-1 and DOS
    CP866 text decoded as Windows-1251 (the classic ``‘Є®а®бвм`` pattern).
    Repair is deliberately conservative: the original text remains a candidate and
    a transformed variant wins only when its readability score is higher.
    """

    text = "" if value is None else str(value)
    text = unicodedata.normalize("NFC", _CONTROL.sub("", text)).replace("\ufffd", "")
    candidates = _repair_candidates(text, rounds=2) if _looks_suspicious(text) else {text}
    best = max(candidates, key=display_text_score)
    best = _SPACES.sub(" ", best).strip()
    return best or fallback


def clean_mnemonic(value: object, *, fallback: str = "CURVE") -> str:
    text = clean_display_text(value, fallback=fallback)
    # LAS mnemonic must stay single-line; spaces are made deterministic.
    text = "_".join(text.split())
    return text or fallback


def display_text_score(text: str) -> tuple[int, int, int, int, int]:
    """Score decoded text without changing it.

    This function is also used by byte-level LAS encoding detection. Higher is
    better; tuple ordering makes the selection deterministic.
    """

    normalized = unicodedata.normalize("NFC", text)
    score = 0
    suspicious = 0
    controls = 0
    printable = 0
    letters = 0

    for character in normalized:
        category = unicodedata.category(character)
        if character == "\ufffd":
            score -= 80
            suspicious += 1
            continue
        if category.startswith("C") and character not in "\r\n\t":
            score -= 30
            controls += 1
            continue
        if character.isprintable() or character in "\r\n\t":
            printable += 1
        if character in _SUSPICIOUS:
            score -= 11
            suspicious += 1
        if character in _ALLOWED_CYRILLIC:
            score += 5
            letters += 1
        elif "CYRILLIC" in unicodedata.name(character, ""):
            # Non-Russian/Kazakh Cyrillic is a strong mojibake indicator here.
            score -= 7
            suspicious += 1
        elif "A" <= character <= "Z" or "a" <= character <= "z":
            score += 4
            letters += 1
        elif character.isdigit():
            score += 2
        elif character.isspace():
            score += 1
        elif category.startswith("L"):
            # Accented Latin and unrelated scripts are possible, but less likely in
            # these LAS descriptions than ASCII/RU/KK text.
            score -= 2

    word_bonus = sum(len(match.group(0)) for match in _WORD.finditer(normalized))
    score += word_bonus * 2
    return (score, letters, printable, -suspicious, -controls)


def _looks_suspicious(text: str) -> bool:
    for character in text:
        if character == "\ufffd" or character in _SUSPICIOUS:
            return True
        if unicodedata.category(character).startswith("C") and character not in "\r\n\t":
            return True
        name = unicodedata.name(character, "")
        if "CYRILLIC" in name and character not in _ALLOWED_CYRILLIC:
            return True
        if character.isalpha() and not (
            character in _ALLOWED_CYRILLIC
            or "A" <= character <= "Z"
            or "a" <= character <= "z"
        ):
            return True
    return False


def _repair_candidates(text: str, *, rounds: int) -> set[str]:
    candidates = {text}
    frontier = {text}
    for _ in range(rounds):
        next_frontier: set[str] = set()
        for candidate in frontier:
            if candidate != text and not _looks_suspicious(candidate):
                continue
            for source_codec, original_codec in _REPAIR_PATHS:
                try:
                    repaired = candidate.encode(source_codec).decode(original_codec)
                except (UnicodeEncodeError, UnicodeDecodeError):
                    continue
                repaired = unicodedata.normalize("NFC", repaired)
                if repaired not in candidates:
                    candidates.add(repaired)
                    next_frontier.add(repaired)
        if not next_frontier:
            break
        frontier = next_frontier
    return candidates
