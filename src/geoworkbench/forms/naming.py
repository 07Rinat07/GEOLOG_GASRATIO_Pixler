from __future__ import annotations

import re
from collections.abc import Iterable

from geoworkbench.forms.models import FormDocument

_WHITESPACE_RE = re.compile(r"\s+")
_SEPARATOR_RE = re.compile(r"[_\-–—]+")

# These names were used by early local builds before the form library acquired
# a naming policy.  Keep the mapping exact enough not to rename arbitrary user
# forms, but tolerant of case, underscores and repeated spaces.
_KNOWN_READY_FORM_NAMES: dict[str, str] = {
    "geo tech gas a4 albom": "Геология, технология и газ — A4, альбомная",
    "geo tech gas logging form a4 albom": (
        "Геолого-технологический газовый каротаж — A4, альбомная"
    ),
    "геология plus под a4 книжная": "Геология Plus — A4, книжная",
    "форма мастерлога под a4 книга": "Мастерлог — A4, книжная",
}


def clean_form_name(value: str) -> str:
    """Return a display-ready form name without accidental spacing.

    The function intentionally preserves the user's letter case and punctuation;
    it only removes leading/trailing whitespace and collapses repeated internal
    whitespace. This keeps geological abbreviations such as ``ЛБА`` intact.
    """

    return _WHITESPACE_RE.sub(" ", str(value).strip())


def normalized_form_name(value: str) -> str:
    """Return a comparison key used to detect duplicate form names."""

    return clean_form_name(value).casefold()


def legacy_ready_form_key(value: str) -> str:
    """Normalize an old local form name for the guarded migration mapping."""

    cleaned = _SEPARATOR_RE.sub(" ", clean_form_name(value).casefold())
    return _WHITESPACE_RE.sub(" ", cleaned).strip()


def polished_ready_form_name(value: str) -> str | None:
    """Return the polished name for a known ready form, or ``None``.

    Only the four names confirmed in the user's existing library are migrated.
    Other user-defined names remain untouched.  Already-polished names also map
    to themselves so a partially completed migration remains idempotent.
    """

    key = legacy_ready_form_key(value)
    direct = _KNOWN_READY_FORM_NAMES.get(key)
    if direct is not None:
        return direct
    return next(
        (name for name in _KNOWN_READY_FORM_NAMES.values() if legacy_ready_form_key(name) == key),
        None,
    )


def duplicate_form_names(
    candidate: str,
    forms: Iterable[FormDocument],
    *,
    exclude_form_id: str | None = None,
) -> tuple[str, ...]:
    """Return existing display names equal to *candidate* after normalization."""

    key = normalized_form_name(candidate)
    if not key:
        return ()
    matches = {
        form.name
        for form in forms
        if form.form_id != exclude_form_id and normalized_form_name(form.name) == key
    }
    return tuple(sorted(matches, key=str.casefold))
