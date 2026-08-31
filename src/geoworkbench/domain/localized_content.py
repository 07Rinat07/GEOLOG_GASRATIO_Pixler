from __future__ import annotations

from collections.abc import Mapping, MutableMapping


SUPPORTED_CONTENT_LANGUAGES: tuple[str, ...] = ("ru", "kk", "en")
UNDETERMINED_CONTENT_LANGUAGE = "und"


def normalize_content_language(language: object, *, allow_undetermined: bool = False) -> str:
    """Return a supported persisted content-language code.

    UI language and authored-content language are deliberately separate.  This
    helper accepts ``AppLanguage`` without importing the UI localization layer.
    """

    value = str(getattr(language, "value", language)).strip().casefold()
    allowed = set(SUPPORTED_CONTENT_LANGUAGES)
    if allow_undetermined:
        allowed.add(UNDETERMINED_CONTENT_LANGUAGE)
    if value not in allowed:
        expected = ", ".join(sorted(allowed))
        raise ValueError(f"Неподдерживаемый язык содержимого: {value!r}; ожидается {expected}")
    return value


def validate_localized_texts(
    values: Mapping[str, str] | None,
    *,
    maximum: int,
    allow_undetermined: bool = True,
) -> dict[str, str]:
    """Validate and normalize a persisted localized-text mapping."""

    if values is None:
        return {}
    if not isinstance(values, Mapping):
        raise ValueError("Многоязычный текст должен быть объектом")
    normalized: dict[str, str] = {}
    for raw_language, raw_text in values.items():
        language = normalize_content_language(
            raw_language, allow_undetermined=allow_undetermined
        )
        if not isinstance(raw_text, str):
            raise ValueError("Значение многоязычного текста должно быть строкой")
        text = raw_text.strip()
        if len(text) > maximum:
            raise ValueError(
                f"Текст для языка {language} превышает допустимые {maximum} символов"
            )
        if text:
            normalized[language] = text
    return normalized


def localized_text(
    values: Mapping[str, str] | None,
    language: object,
    *,
    legacy: str | None = None,
) -> str:
    """Resolve authored text without silently translating it.

    The requested language wins.  Legacy/undetermined content is the explicit
    compatibility fallback, followed by Russian and the first available value.
    """

    requested = normalize_content_language(language)
    source = values or {}
    for key in (requested, UNDETERMINED_CONTENT_LANGUAGE, "ru", "kk", "en"):
        value = source.get(key)
        if isinstance(value, str) and value.strip():
            return value
    return legacy or ""


def set_localized_text(
    values: MutableMapping[str, str],
    language: object,
    text: str | None,
    *,
    maximum: int,
) -> bool:
    """Set or clear one language and report whether persisted content changed."""

    code = normalize_content_language(language)
    if text is not None and not isinstance(text, str):
        raise ValueError("Текст должен быть строкой или null")
    normalized = (text or "").strip()
    if len(normalized) > maximum:
        raise ValueError(f"Текст превышает допустимые {maximum} символов")
    previous = values.get(code)
    if normalized:
        values[code] = normalized
    else:
        values.pop(code, None)
    return previous != (normalized or None)


def bump_language_revision(revisions: MutableMapping[str, int], language: object) -> int:
    code = normalize_content_language(language)
    current = revisions.get(code, 0)
    if isinstance(current, bool) or not isinstance(current, int) or current < 0:
        current = 0
    revisions[code] = current + 1
    return revisions[code]
