"""Editable A4 Masterlog headers assembled from existing catalog elements."""
from __future__ import annotations

from functools import lru_cache
from hashlib import sha256

from geoworkbench.domain.models import MasterlogHeaderElement
from geoworkbench.form_constructor.asset_install import load_factory_constructor_registry
from geoworkbench.printing.image_assets import ImageAsset, PNG_MEDIA_TYPE
from geoworkbench.printing.logo_catalog import builtin_logo_definition


SYMBOL_IDS = (
    "symbol-loss", "symbol-influx", "symbol-oil-saturation",
    "symbol-weak-oil-show", "symbol-residual-oil-saturation",
    "symbol-core", "symbol-core-hydrocarbon-shows", "symbol-background-gas",
    "symbol-formation-gas", "symbol-tripping-gas", "symbol-test-gas", "symbol-co2",
)


@lru_cache(maxsize=1)
def masterlog_header_assets() -> dict[str, ImageAsset]:
    logo = builtin_logo_definition("factory-bpservices").create_asset()
    result = {"bpservices": logo}
    registry = load_factory_constructor_registry()
    for item in registry.all(kind="depth_symbol"):
        if item.asset_id in SYMBOL_IDS:
            payload = item.asset_path.read_bytes()
            result[item.asset_id] = ImageAsset(
                f"sha256:{sha256(payload).hexdigest()}", item.asset_path.name,
                PNG_MEDIA_TYPE, payload,
            )
    return result


def default_header_asset(asset_ref: str) -> ImageAsset | None:
    return next((a for a in masterlog_header_assets().values() if a.asset_id == asset_ref), None)


def masterlog_header_elements(orientation: str) -> tuple[MasterlogHeaderElement, ...]:
    portrait = orientation == "portrait"
    width, height = (210.0, 140.0) if portrait else (297.0, 100.0)
    left, right = 5.0, width - 5.0
    usable = right - left
    top = 19.0 if portrait else 15.0
    row_h = 5.4 if portrait else 3.8
    meta_end = top + 7 * row_h
    legend_y = meta_end + 2
    legend_h = 43.0 if portrait else 32.0
    bottom_y = legend_y + legend_h + 1
    font = 1.8 if portrait else 2.0
    elements: list[MasterlogHeaderElement] = []

    def add(key, kind, x, y, w, h, **props):
        elements.append(MasterlogHeaderElement(key, kind, x, y, w, h, props))

    def label(key, texts, x, y, w, h, **props):
        add(key, "text", x, y, w, h, text=texts[0], text_ru=texts[0],
            text_kk=texts[1], text_en=texts[2], font_size_mm=font,
            color="#000080", **props)

    add("customer_logo", "image", left+2, 2, usable*.22, top-4,
        optional=True, logo_role="customer", mode="fit", placeholder_text="",
        placeholder_text_ru="", placeholder_text_kk="", placeholder_text_en="")
    add("contractor_logo", "image", right-usable*.22-2, 2, usable*.22, top-4,
        asset_ref=masterlog_header_assets()["bpservices"].asset_id,
        optional=True, logo_role="contractor", mode="fit")
    label("title", ("Мастерлог", "Мастерлог", "Masterlog"), width*.3, 1, width*.4, 5,
          bold=True, alignment="center")
    label("interval_title", ("Интервал исследований, м", "Зерттеу аралығы, м", "Survey interval, m"),
          width*.28, 6, width*.44, 4, alignment="center", bold=True)
    for key, x in (("interval_start", width*.36), ("interval_end", width*.51)):
        add(key, "field", x, 10, width*.13, 4, field=f"header.{key}",
            missing_text="", font_size_mm=font, color="#000080", alignment="center")
    label("interval_separator", ("-", "-", "-"), width*.49, 10, width*.02, 4, alignment="center")

    rows = (
        (("Страна", "Ел", "Country", "country"), ("Заказчик", "Тапсырыс беруші", "Customer", "customer"), ("Скважина", "Ұңғыма", "Well", "well_number")),
        (("Участок", "Учаске", "Block", "district"), ("Исполнитель", "Орындаушы", "Contractor", "contractor"), ("Буровая компания", "Бұрғылау компаниясы", "Drilling company", "drilling_company")),
        (("Вид скважины", "Ұңғыма түрі", "Well type", "well_type"), ("Масштаб", "Масштаб", "Scale", "scale"), ("Буровая установка", "Бұрғылау қондырғысы", "Drilling rig", "rig")),
        (("Проектная глубина, м", "Жобалық тереңдік, м", "Planned depth, m", "project_depth"), ("Начало бурения", "Бұрғылау басталуы", "Spud date", "start_date"), ("Высота ротора, м", "Ротор биіктігі, м", "Rig floor, m", "rig_floor")),
        (("Фактическая глубина, м", "Нақты тереңдік, м", "Actual depth, m", "actual_depth"), ("Конец бурения", "Бұрғылау аяқталуы", "Completion date", "end_date"), ("Альтитуда устья, м", "Саға биіктігі, м", "Wellhead elevation, m", "wellhead_altitude")),
        (("Инженеры", "Инженерлер", "Engineers", "engineers"), ("Геологи", "Геологтар", "Geologists", "geologists"), ("Широта", "Ендік", "Latitude", "latitude")),
        (("", "", "", None), ("", "", "", None), ("Долгота", "Бойлық", "Longitude", "longitude")),
    )
    add("metadata_frame", "text", left, top, usable, 7*row_h, text="", frame=True)
    for r, row in enumerate(rows):
        for c, entry in enumerate(row):
            ru, kk, en, field = entry
            if field is None:
                continue
            x, group = left + c*usable/3, usable/3
            h = 2*row_h if field in {"engineers", "geologists"} else row_h
            label(f"label_{field}", (ru, kk, en), x+1, top+r*row_h, group*.49-1, row_h, bold=True)
            add(f"value_{field}", "field", x+group*.49, top+r*row_h, group*.51-1, h,
                field=f"header.{field}", missing_text="", font_size_mm=font,
                color="#000080", text_position="top")
    for r in (3, 5):
        add(f"metadata_rule_{r}", "line", left, top+r*row_h, usable, 0, color="#222222", width=.2)

    legend_w = usable*.66
    registry = load_factory_constructor_registry()
    rock_ids = [a.asset_id for a in registry.all(kind="lithology_pattern") if a.asset_id in {
        "lithology-anhydrite", "lithology-breccia", "lithology-clay", "lithology-claystone",
        "lithology-coal", "lithology-conglomerate", "lithology-dolomite", "lithology-chalk",
        "lithology-sand", "lithology-sandstone", "lithology-limestone", "lithology-siltstone",
        "lithology-granite", "lithology-gravel", "lithology-gypsum", "lithology-marl",
    }]
    add("rock_legend", "lithology_legend", left, legend_y, legend_w, legend_h,
        scope="manual", selected_lithotype_ids=rock_ids, columns=3 if portrait else 4,
        show_code=False, font_size_mm=font, color="#000080")
    add("lba_legend", "lba_legend", left+legend_w+1, legend_y, usable-legend_w-1, legend_h,
        compact=True, font_size_mm=font, color="#000080")
    symbols_w = legend_w
    add("symbols_frame", "text", left, bottom_y, symbols_w, height-bottom_y-2, text="", frame=True)
    definitions = {a.asset_id: a for a in registry.all(kind="depth_symbol")}
    for i, key in enumerate(SYMBOL_IDS):
        col, row_index = divmod(i, 6)
        cell_w, cell_h = symbols_w/2, (height-bottom_y-2)/6
        x, y = left + col*cell_w, bottom_y + row_index*cell_h
        swatch = min(4.0, cell_h-.4)
        add(key, "image", x+1, y+.2, swatch, swatch,
            asset_ref=masterlog_header_assets()[key].asset_id, mode="fit")
        asset = definitions[key]
        label(f"{key}_label", tuple(asset.display_name(lang) for lang in ("ru", "kk", "en")),
              x+swatch+2, y, cell_w-swatch-3, cell_h)

    x, w = left+legend_w+1, usable-legend_w-1
    add("construction_frame", "text", x, bottom_y, w, height-bottom_y-2, text="", frame=True)
    label("construction_title", ("КОНСТРУКЦИЯ СКВАЖИНЫ", "ҰҢҒЫМА КОНСТРУКЦИЯСЫ", "WELL CONSTRUCTION"),
          x+1, bottom_y, w-2, 4, alignment="center", bold=True)
    construction = (
        ("762", ("Направление", "Бағыттаушы", "Drive pipe"), "44,65"),
        ("473,08", ("Кондуктор", "Кондуктор", "Surface casing"), "709"),
        ("339,72", ("1-я промежуточная кол.", "1-аралық бағана", "1st intermediate"), "2388,6"),
        ("250,83", ("2-я промежуточная кол.", "2-аралық бағана", "2nd intermediate"), "3856,5"),
        ("177,8", ("Эксплуатационная кол.", "Пайдалану бағанасы", "Production casing"), "5029,78"),
    )
    ch = (height-bottom_y-6)/5
    for i, (diameter, names, depth) in enumerate(construction):
        y = bottom_y+4+i*ch
        label(f"casing_{i}_diameter", (f"Ø {diameter} мм", f"Ø {diameter} мм", f"Ø {diameter} mm"), x+1, y, w*.24, ch)
        label(f"casing_{i}_name", names, x+w*.25, y, w*.49, ch)
        label(f"casing_{i}_depth", (f"{depth} м", f"{depth} м", f"{depth} m"), x+w*.75, y, w*.24-1, ch)
        for element in elements[-3:]:
            # Retain sample text for projects which have not adopted a passport.
            element.element_type = "field"
            element.properties["field"] = f"header.{element.element_id}"
    return tuple(elements)
