import json

import pytest

from geoworkbench.catalogs.lithotypes import load_lithotype_catalog


def test_builtin_lithotype_catalog_is_valid_and_unique() -> None:
    catalog = load_lithotype_catalog()

    assert len(catalog) >= 15
    assert len({item.lithotype_id for item in catalog}) == len(catalog)
    sandstone = next(item for item in catalog if item.lithotype_id == "sandstone")
    assert sandstone.name_ru == "Песчаник"
    assert sandstone.pattern_key == "sandstone_bricks"


def test_lithotype_catalog_rejects_duplicate_ids(tmp_path) -> None:
    path = tmp_path / "catalog.json"
    entry = {
        "id": "clay",
        "name_ru": "Глина",
        "name_en": "Clay",
        "category": "sedimentary",
        "color": "#00ff00",
        "pattern_key": "clay_dash",
    }
    path.write_text(
        json.dumps({"schema_version": 1, "lithotypes": [entry, entry]}),
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="Повторяющийся"):
        load_lithotype_catalog(path)
