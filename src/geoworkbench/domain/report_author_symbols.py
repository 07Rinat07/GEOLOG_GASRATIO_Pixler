"""Stable renderer-independent author symbol identifiers."""
from enum import StrEnum


class AuthorSymbolId(StrEnum):
    CIRCLE = "circle"
    SQUARE = "square"
    DIAMOND = "diamond"
    TRIANGLE = "triangle"
    CROSS = "cross"


