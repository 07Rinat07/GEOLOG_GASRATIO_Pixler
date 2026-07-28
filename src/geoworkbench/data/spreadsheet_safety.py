from __future__ import annotations

import unicodedata
from collections.abc import Iterable

_FORMULA_PREFIXES = frozenset("=+-@")
_IGNORED_LEADING_CATEGORIES = frozenset({"Cc", "Cf"})


def protect_spreadsheet_value(value: object) -> object:
    """Return text that spreadsheet applications cannot interpret as a formula.

    Numeric values, dates and safe strings are returned unchanged.  A leading
    apostrophe is added only when the first character after whitespace or control
    characters is a spreadsheet formula prefix.
    """

    if not isinstance(value, str):
        return value
    for character in value:
        category = unicodedata.category(character)
        if character.isspace() or category in _IGNORED_LEADING_CATEGORIES:
            continue
        return f"'{value}" if character in _FORMULA_PREFIXES else value
    return value


def protect_spreadsheet_row(values: Iterable[object]) -> tuple[object, ...]:
    return tuple(protect_spreadsheet_value(value) for value in values)
