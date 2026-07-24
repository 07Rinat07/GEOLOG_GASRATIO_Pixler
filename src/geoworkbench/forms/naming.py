from __future__ import annotations

import re
from collections.abc import Iterable

from geoworkbench.forms.models import FormDocument

_WHITESPACE_RE = re.compile(r"\s+")


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
