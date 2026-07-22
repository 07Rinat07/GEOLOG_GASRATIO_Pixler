from __future__ import annotations

from pathlib import Path

from .models import ParadoxBundle


_COMPANIONS = {".px": "primary_index", ".tv": "table_view", ".fam": "family"}


def discover_bundle(path: str | Path) -> ParadoxBundle:
    """Find same-stem Paradox companion files without changing the source.

    Extension comparison is case-insensitive.  The exact selected DB stem is
    retained; this prevents an unrelated table in the same directory from being
    attached accidentally.
    """

    main = Path(path).expanduser().resolve()
    directory = main.parent
    stem = main.stem.casefold()
    found: dict[str, Path] = {}
    try:
        entries = tuple(directory.iterdir())
    except OSError:
        entries = ()
    for entry in entries:
        if not entry.is_file() or entry.stem.casefold() != stem:
            continue
        attribute = _COMPANIONS.get(entry.suffix.casefold())
        if attribute is not None:
            found[attribute] = entry.resolve()
    return ParadoxBundle(main=main, **found)
