from __future__ import annotations

from dataclasses import dataclass
from functools import lru_cache
import re
import unicodedata

from PySide6.QtGui import QFont, QFontDatabase, QFontMetrics
from PySide6.QtWidgets import QApplication, QComboBox, QTabWidget, QWidget


class UnicodePrintError(RuntimeError):
    """Raised when text cannot be printed safely without corrupt glyphs."""


# Russian, Kazakh, English and frequently used engineering/geological symbols.
_REQUIRED_PRINT_SAMPLE = (
    "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789 "
    "АБВГДЕЁЖЗИЙКЛМНОПРСТУФХЦЧШЩЪЫЬЭЮЯ"
    "абвгдеёжзийклмнопрстуфхцчшщъыьэюя"
    "ӘәҒғҚқҢңӨөҰұҮүҺһІі"
    "°±×÷≤≥≈≠∞µΩΔΣΦφλρ²³₁₂₃–—…№%‰/()[]{}:;,.+-_@#"
)

_PREFERRED_FAMILIES = (
    "Noto Sans",
    "Noto Sans Display",
    "DejaVu Sans",
    "Segoe UI",
    "Arial",
    "Liberation Sans",
    "Ubuntu",
    "FreeSans",
)

_SUSPICIOUS_MOJIBAKE_MARKERS = (
    "ï¿½",
    "â€™",
    "â€œ",
    "â€",
    "Â°",
    "Â±",
    "Ã©",
    "Ã¨",
    "Ã±",
)

# Typical UTF-8 Cyrillic bytes decoded as Windows-1252/Latin-1 produce repeated
# pairs such as ``Ð“Ð»ÑƒÐ±Ð¸Ð½Ð°``. Two or more adjacent pairs are a strong
# corruption signal while a single legitimate Latin letter Ð/Ñ is not.
_CYRILLIC_MOJIBAKE_PATTERN = re.compile(r"(?:[ÐÑ].){2,}")


@dataclass(frozen=True, slots=True)
class UnicodeFontProfile:
    families: tuple[str, ...]
    primary_family: str
    required_sample_supported: bool
    missing_required_characters: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class UnicodePreflightReport:
    text_count: int
    character_count: int
    font_profile: UnicodeFontProfile
    invalid_fragments: tuple[str, ...] = ()
    missing_glyphs: tuple[str, ...] = ()
    suspicious_fragments: tuple[str, ...] = ()

    @property
    def ok(self) -> bool:
        return (
            not self.invalid_fragments
            and not self.missing_glyphs
            and not self.suspicious_fragments
        )

    def error_message(self) -> str:
        parts: list[str] = []
        if self.invalid_fragments:
            parts.append(
                "Обнаружен повреждённый Unicode-текст: " + "; ".join(self.invalid_fragments[:8])
            )
        if self.suspicious_fragments:
            parts.append(
                "Обнаружен текст с признаками ошибочной перекодировки: "
                + "; ".join(repr(item) for item in self.suspicious_fragments[:8])
            )
        if self.missing_glyphs:
            rendered = " ".join(_describe_character(item) for item in self.missing_glyphs[:20])
            parts.append("В установленных шрифтах отсутствуют символы: " + rendered)
        if not self.font_profile.required_sample_supported:
            parts.append(
                "Не найден один шрифт, полностью поддерживающий русский, қазақша, "
                "английский и инженерные символы. Установите Noto Sans, DejaVu Sans "
                "или Segoe UI и повторите печать."
            )
        return "\n".join(parts) or "Unicode-проверка не пройдена"


def configure_application_unicode_fonts(app: QApplication) -> UnicodeFontProfile:
    """Choose a scalable Unicode font stack before any UI is constructed.

    Qt uses Unicode internally, but a PDF can only contain readable text when a
    font with the required glyphs is available.  A family stack gives Qt a
    deterministic cross-platform fallback order while still allowing the
    platform font matcher to handle additional installed scripts.
    """

    profile = resolve_unicode_font_profile(_REQUIRED_PRINT_SAMPLE)
    font = QFont(app.font())
    if hasattr(font, "setFamilies"):
        font.setFamilies(list(profile.families))
    elif profile.primary_family:
        font.setFamily(profile.primary_family)
    font.setStyleStrategy(QFont.StyleStrategy.PreferAntialias)
    app.setFont(font)
    return profile


def resolve_unicode_font_profile(text: str = _REQUIRED_PRINT_SAMPLE) -> UnicodeFontProfile:
    installed = _installed_font_families()
    if not installed:
        system = QFontDatabase.systemFont(QFontDatabase.SystemFont.GeneralFont).family()
        return UnicodeFontProfile((system,), system, False, tuple(_unique_printable(text)))

    ordered: list[str] = []
    lookup = {family.casefold(): family for family in installed}
    for preferred in _PREFERRED_FAMILIES:
        actual = lookup.get(preferred.casefold())
        if actual and actual not in ordered:
            ordered.append(actual)

    system_family = QFontDatabase.systemFont(QFontDatabase.SystemFont.GeneralFont).family()
    if system_family in installed and system_family not in ordered:
        ordered.append(system_family)

    required = tuple(_unique_printable(text))

    # The common case must be fast: a preferred family such as Noto Sans,
    # DejaVu Sans or Segoe UI already covers all RU/KK/EN engineering text.
    # Returning immediately avoids ranking every installed font for every PDF.
    complete = next((family for family in ordered if _supports_all(family, required)), None)
    if complete is not None:
        fallback = [complete, *(family for family in ordered if family != complete)]
        return UnicodeFontProfile(
            tuple(fallback[:8]),
            complete,
            True,
            (),
        )

    selected: list[str] = []
    remaining = set(required)
    candidates = [*ordered, *(family for family in installed if family not in ordered)]
    while remaining and len(selected) < 8:
        best_family = ""
        best_covered: set[str] = set()
        for family in candidates:
            if family in selected:
                continue
            covered = {
                character
                for character in remaining
                if _family_supports(family, ord(character))
            }
            if len(covered) > len(best_covered):
                best_family = family
                best_covered = covered
                if len(best_covered) == len(remaining):
                    break
        if not best_family or not best_covered:
            break
        selected.append(best_family)
        remaining.difference_update(best_covered)

    if not selected:
        selected = [system_family or installed[0]]

    return UnicodeFontProfile(
        tuple(selected),
        selected[0],
        False,
        tuple(sorted(remaining, key=ord)),
    )


def preflight_widget_unicode(widget: QWidget) -> UnicodePreflightReport:
    texts = collect_widget_text(widget)
    return preflight_texts(texts)


def ensure_widget_printable_unicode(widget: QWidget) -> UnicodePreflightReport:
    report = preflight_widget_unicode(widget)
    if not report.ok:
        raise UnicodePrintError(report.error_message())
    return report


def preflight_texts(texts: tuple[str, ...] | list[str]) -> UnicodePreflightReport:
    normalized = tuple(text for text in texts if isinstance(text, str) and text)
    invalid: list[str] = []
    suspicious: list[str] = []
    characters: list[str] = []
    for text in normalized:
        problems = _text_integrity_problems(text)
        if problems:
            invalid.append(f"{_shorten(text)!r}: {', '.join(problems)}")
        if any(marker in text for marker in _SUSPICIOUS_MOJIBAKE_MARKERS) or (
            _CYRILLIC_MOJIBAKE_PATTERN.search(text) is not None
        ):
            suspicious.append(_shorten(text))
        characters.extend(_unique_printable(text))

    unique_characters = tuple(dict.fromkeys(characters))
    profile = resolve_unicode_font_profile("".join(unique_characters) or _REQUIRED_PRINT_SAMPLE)
    # ``resolve_unicode_font_profile`` already examines installed font coverage
    # and returns only characters that no selected fallback can render.
    missing = profile.missing_required_characters
    return UnicodePreflightReport(
        text_count=len(normalized),
        character_count=sum(len(text) for text in normalized),
        font_profile=profile,
        invalid_fragments=tuple(invalid),
        missing_glyphs=missing,
        suspicious_fragments=tuple(dict.fromkeys(suspicious)),
    )


def collect_widget_text(widget: QWidget) -> tuple[str, ...]:
    """Collect visible UI strings without serialising binary or plot data."""

    values: list[str] = []
    objects = (widget, *widget.findChildren(QWidget))
    for item in objects:
        if not item.isVisibleTo(widget) and item is not widget:
            continue
        for attribute in ("text", "title", "windowTitle", "placeholderText", "toolTip"):
            method = getattr(item, attribute, None)
            if not callable(method):
                continue
            try:
                value = method()
            except (RuntimeError, TypeError):
                continue
            if isinstance(value, str) and value.strip():
                values.append(value)
        if isinstance(item, QComboBox):
            values.extend(item.itemText(index) for index in range(item.count()))
        if isinstance(item, QTabWidget):
            values.extend(item.tabText(index) for index in range(item.count()))

    return tuple(dict.fromkeys(value for value in values if value))


def print_font(
    point_size: float = 8.0,
    *,
    bold: bool = False,
    text: str = _REQUIRED_PRINT_SAMPLE,
) -> QFont:
    app = QApplication.instance()
    base = QFont(app.font()) if isinstance(app, QApplication) else QFont()
    # Resolve the font stack for the actual string being drawn. This keeps
    # Arabic, CJK and other installed scripts safe in vector PDF headers rather
    # than relying only on the RU/KK/EN default sample.
    profile = resolve_unicode_font_profile(text or _REQUIRED_PRINT_SAMPLE)
    if hasattr(base, "setFamilies"):
        base.setFamilies(list(profile.families))
    elif profile.primary_family:
        base.setFamily(profile.primary_family)
    base.setPointSizeF(point_size)
    base.setBold(bold)
    base.setStyleStrategy(QFont.StyleStrategy.PreferAntialias)
    return base


def _text_integrity_problems(text: str) -> tuple[str, ...]:
    problems: list[str] = []
    try:
        text.encode("utf-8", errors="strict").decode("utf-8", errors="strict")
    except UnicodeError:
        problems.append("невалидная последовательность UTF-8/Unicode")
    if "\ufffd" in text:
        problems.append("символ замены U+FFFD")
    if any(0xD800 <= ord(character) <= 0xDFFF for character in text):
        problems.append("непарный суррогат Unicode")
    controls = [
        character
        for character in text
        if unicodedata.category(character) == "Cc" and character not in "\n\r\t"
    ]
    if controls:
        problems.append("недопустимые управляющие символы")
    return tuple(problems)


def _unique_printable(text: str):
    seen: set[str] = set()
    for character in text:
        category = unicodedata.category(character)
        if character.isspace() or category in {"Cc", "Cf", "Cs"}:
            continue
        if character not in seen:
            seen.add(character)
            yield character


def _supports_all(family: str, characters: tuple[str, ...]) -> bool:
    return all(_family_supports(family, ord(character)) for character in characters)


def _installed_font_families() -> tuple[str, ...]:
    # QFontDatabase can legitimately be empty before QApplication has finished
    # initialising.  Never cache that transient result: doing so makes every
    # later print preflight fail for the lifetime of the process.
    return tuple(QFontDatabase.families())


@lru_cache(maxsize=65536)
def _family_supports(family: str, codepoint: int) -> bool:
    # Cache only the Python bool. Keeping QFontMetrics instances alive past the
    # QApplication lifetime can crash Qt during interpreter shutdown.
    try:
        return bool(QFontMetrics(QFont(family)).inFontUcs4(codepoint))
    except (OverflowError, RuntimeError, TypeError):
        return False


def _describe_character(character: str) -> str:
    name = unicodedata.name(character, "UNKNOWN")
    return f"{character!r} (U+{ord(character):04X}, {name})"


def _shorten(value: str, limit: int = 80) -> str:
    compact = " ".join(value.split())
    return compact if len(compact) <= limit else compact[: limit - 1] + "…"
