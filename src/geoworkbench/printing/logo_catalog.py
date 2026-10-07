from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256
from importlib.resources import files

from geoworkbench.brand import REPORT_BRAND_WORDMARK
from geoworkbench.printing.image_assets import (
    ImageAsset,
    SVG_MEDIA_TYPE,
    create_raster_payload_asset,
)


@dataclass(frozen=True, slots=True)
class BuiltinLogoDefinition:
    logo_id: str
    name_ru: str
    name_kk: str
    name_en: str
    category_ru: str
    category_kk: str
    category_en: str
    resource_name: str
    notes_ru: str = ""
    notes_kk: str = ""
    notes_en: str = ""

    def name(self, language: str) -> str:
        return {
            "kk": self.name_kk,
            "en": self.name_en,
        }.get(language, self.name_ru)

    def category(self, language: str) -> str:
        return {
            "kk": self.category_kk,
            "en": self.category_en,
        }.get(language, self.category_ru)

    def notes(self, language: str) -> str:
        return {
            "kk": self.notes_kk,
            "en": self.notes_en,
        }.get(language, self.notes_ru)

    def create_asset(self) -> ImageAsset:
        payload = files("geoworkbench.resources").joinpath(self.resource_name).read_bytes()
        if not self.resource_name.casefold().endswith(".svg"):
            return create_raster_payload_asset(payload, original_name=self.resource_name)

        digest = sha256(payload).hexdigest()
        return ImageAsset(
            asset_id=f"sha256:{digest}",
            original_name=self.resource_name,
            media_type=SVG_MEDIA_TYPE,
            payload=payload,
        )


BUILTIN_LOGOS: tuple[BuiltinLogoDefinition, ...] = (
    BuiltinLogoDefinition(
        logo_id="factory-digital-geolog",
        name_ru=REPORT_BRAND_WORDMARK,
        name_kk=REPORT_BRAND_WORDMARK,
        name_en=REPORT_BRAND_WORDMARK,
        category_ru="Бренд приложения",
        category_kk="Қолданба бренді",
        category_en="Application brand",
        resource_name="digital-geolog-logo.jpg",
        notes_ru="Финальный логотип DIGITAL GEOLOG для печатных шапок и экспорта.",
        notes_kk="Баспа тақырыптары мен экспортқа арналған DIGITAL GEOLOG соңғы логотипі.",
        notes_en="Final DIGITAL GEOLOG logo for print headers and exports.",
    ),
    BuiltinLogoDefinition(
        logo_id="factory-bpservices",
        name_ru="BPServices",
        name_kk="BPServices",
        name_en="BPServices",
        category_ru="Исполнитель",
        category_kk="Орындаушы",
        category_en="Contractor",
        resource_name="bpservices_logo.png",
        notes_ru="Подготовленный логотип с полем около 1 мм для печатных шапок.",
        notes_kk="Баспа тақырыптары үшін шамамен 1 мм жиегі бар дайын логотип.",
        notes_en="Prepared logo with an approximately 1 mm margin for print headers.",
    ),
)


def builtin_logo_definition(logo_id: str) -> BuiltinLogoDefinition:
    try:
        return next(item for item in BUILTIN_LOGOS if item.logo_id == logo_id)
    except StopIteration as exc:
        raise KeyError(logo_id) from exc
