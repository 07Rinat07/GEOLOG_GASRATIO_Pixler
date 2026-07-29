from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256
from importlib.resources import files

from geoworkbench.printing.image_assets import ImageAsset, PNG_MEDIA_TYPE


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
        digest = sha256(payload).hexdigest()
        return ImageAsset(
            asset_id=f"sha256:{digest}",
            original_name=self.resource_name,
            media_type=PNG_MEDIA_TYPE,
            payload=payload,
        )


BUILTIN_LOGOS: tuple[BuiltinLogoDefinition, ...] = (
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
