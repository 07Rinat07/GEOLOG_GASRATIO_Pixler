from __future__ import annotations

from geoworkbench.forms.templates import localized_factory_label
from geoworkbench.project.lithotype_catalog_models import CatalogLithotype
from geoworkbench.services.geology_labels import (
    localized_lithotype_name,
    localized_rock_text,
)
from geoworkbench.services.localization import AppLanguage
from geoworkbench.services.parameter_labels import localized_curve_name


def test_known_factory_titles_retranslate_without_changing_saved_text() -> None:
    assert localized_factory_label("Бурение", AppLanguage.KK) == "Бұрғылау"
    assert localized_factory_label("Бурение", AppLanguage.EN) == "Drilling"
    assert localized_factory_label("Описание пород", AppLanguage.KK) == (
        "Тау жыныстарының сипаттамасы"
    )
    assert localized_factory_label("Описание пород", AppLanguage.EN) == "Rock description"
    assert localized_factory_label("Технология", AppLanguage.EN) == "Technology"
    assert localized_factory_label("Газ C1-C5", AppLanguage.EN) == "C1–C5 gas"


def test_generated_split_column_suffix_is_preserved_after_translation() -> None:
    assert localized_factory_label("Бурение 2", AppLanguage.KK) == "Бұрғылау 2"
    assert localized_factory_label("Бурение 3", AppLanguage.EN) == "Drilling 3"


def test_unknown_user_caption_is_not_translated_or_modified() -> None:
    caption = "Моя авторская колонка"
    assert localized_factory_label(caption, AppLanguage.KK) == caption
    assert localized_factory_label(caption, AppLanguage.EN) == caption


def test_standard_catalog_caption_does_not_block_curve_translation() -> None:
    assert localized_curve_name(
        "S300",
        description="Давление на манифольде",
        unit="атм",
        configured="Давление на манифольде",
        language=AppLanguage.EN,
    ) == "Standpipe Pressure"
    assert localized_curve_name(
        "S300",
        description="Давление на манифольде",
        unit="атм",
        configured="Давление на манифольде",
        language=AppLanguage.KK,
    ) == "Айдау қысымы"


def test_lithotype_names_follow_active_language_but_free_text_is_preserved() -> None:
    sandstone = CatalogLithotype(
        lithotype_id="sandstone",
        code="SST",
        name_ru="Песчаник",
        name_en="Sandstone",
        name_kk="Құмтас",
        category="sedimentary",
        color="#d6b36a",
        pattern_key="sandstone",
        system=True,
    )

    assert localized_lithotype_name(sandstone, AppLanguage.KK) == "Құмтас"
    assert localized_lithotype_name(sandstone, AppLanguage.EN) == "Sandstone"
    assert localized_rock_text("Песчаник", (sandstone,), AppLanguage.EN) == "Sandstone"
    assert localized_rock_text("Песчаник мелкозернистый", (sandstone,), AppLanguage.EN) == (
        "Песчаник мелкозернистый"
    )


def test_tablet_source_routes_titles_parameters_and_rocks_through_localizers() -> None:
    from pathlib import Path

    source = (
        Path(__file__).resolve().parents[1]
        / "src/geoworkbench/tablet/tablet_view.py"
    ).read_text(encoding="utf-8")

    assert "localized_title = localized_factory_label(" in source
    assert "definition.title," in source
    assert "localized_factory_label(title, self._localizer.language)" in source
    assert "configured = localized_factory_label(" in source
    assert "localized_lithotype_name(" in source
    assert "localized_rock_text(" in source
    assert "lithotype.name_ru if lithotype is not None" not in source
