from __future__ import annotations

from collections.abc import Iterable

from geoworkbench.project.lithotype_catalog_models import CatalogLithotype
from geoworkbench.services.localization import AppLanguage


def localized_lithotype_name(
    lithotype: CatalogLithotype | None,
    language: AppLanguage | str,
    fallback: str = "",
) -> str:
    """Return a catalog rock name in the active UI language.

    The persisted geology record remains language-neutral and unchanged. Unknown
    custom lithotype IDs use the supplied fallback instead of inventing a label.
    """

    if lithotype is None:
        return fallback
    code = language.value if isinstance(language, AppLanguage) else str(language)
    return lithotype.localized_name(code) or fallback


def localized_rock_text(
    value: str,
    catalog: Iterable[CatalogLithotype],
    language: AppLanguage | str,
) -> str:
    """Translate an exact catalog rock name while preserving free-form notes.

    Automatic translation is intentionally conservative: only a value equal to
    one of the catalog's RU/KK/EN rock names is replaced. Geological prose and
    user comments are never machine-translated or modified silently.
    """

    original = str(value)
    normalized = " ".join(original.split()).casefold()
    if not normalized:
        return original
    for lithotype in catalog:
        aliases = {
            " ".join(name.split()).casefold()
            for name in (lithotype.name_ru, lithotype.name_kk, lithotype.name_en)
            if name
        }
        if normalized in aliases:
            return localized_lithotype_name(lithotype, language, original)
    return original
