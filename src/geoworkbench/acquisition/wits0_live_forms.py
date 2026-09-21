from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass

from geoworkbench.catalogs.sensors import normalize_sensor_key


CUSTOM_LIVE_FORM_ID = "custom"
UNIVERSAL_LIVE_FORM_ID = "universal"


@dataclass(frozen=True, slots=True)
class Wits0LiveFormDefinition:
    """A named projection of engineering channels for the WITS0 live workspace."""

    form_id: str
    title_ru: str
    title_kk: str
    title_en: str
    channel_keys: tuple[str, ...]
    custom: bool = False

    def title(self, language: object) -> str:
        code = str(getattr(language, "value", language)).strip().casefold()
        if code == "kk":
            return self.title_kk
        if code == "en":
            return self.title_en
        return self.title_ru


_CHANNEL_ALIASES: dict[str, tuple[str, ...]] = {
    "hole_depth": ("HOLE_DEPTH", "DEPTMEAS", "DEPTH", "MD"),
    "bit_depth": ("BIT_DEPTH", "DEPTBITM", "BDEP"),
    "bit_distance": ("BIT_DISTANCE_TO_BOTTOM", "DIST_TO_BOTTOM"),
    "block_position": ("BLOCK_POSITION", "BLKPOS", "BPOS"),
    "block_speed": ("BLOCK_SPEED", "BVEL"),
    "rop": ("ROP", "ROPA", "ROP_AVG"),
    "lag_time": ("LAG_TIME", "LAG"),
    "hook_load": ("HKLD", "HKLA", "HKLX", "HOOKLOAD"),
    "string_weight": ("STRING_WEIGHT", "STRGWT", "STWT"),
    "wob": ("WOB", "WOBA", "WOBX", "WEIGHT_ON_BIT"),
    "rpm": ("RPM", "RPMA", "ROTARY_SPEED"),
    "torque": ("TQ", "TORQUE", "TORQA", "TORQX", "ROTARY_TORQUE"),
    "spp": ("SPP", "SPPA", "STANDPIPE_PRESSURE"),
    "pump_1": ("SENSOR_50", "SPM1"),
    "pump_2": ("SENSOR_51", "SPM2"),
    "pump_3": ("SENSOR_52", "SPM3"),
    "flow_in": ("FLOW_IN", "MFIA", "QIN"),
    "flow_out": ("FLOW_OUT", "MFOA", "MFOP", "QOUT"),
    "mud_density_in": ("MW_IN", "MDIA", "MUD_DENSITY_IN"),
    "mud_density_out": ("MW_OUT", "MDOA", "MUD_DENSITY_OUT"),
    "mud_temp_in": ("TEMP_IN", "MTIA", "MUD_TEMP_IN"),
    "mud_temp_out": ("TEMP_OUT", "MTOA", "MUD_TEMP_OUT"),
    "pit_total": ("PIT_VOL", "TVOLACT", "TVOLTOT", "PVT"),
    "pit_1": ("SENSOR_711", "TVOL01", "PIT1"),
    "pit_2": ("SENSOR_712", "TVOL02", "PIT2"),
    "pit_3": ("SENSOR_713", "TVOL03", "PIT3"),
    "pit_4": ("SENSOR_716", "TVOL04", "PIT4"),
    "pit_5": ("SENSOR_717", "TVOL05", "PIT5"),
    "pit_6": ("SENSOR_718", "TVOL06", "PIT6"),
    "pit_7": ("SENSOR_723", "TVOL07", "PIT7"),
    "pit_8": ("SENSOR_724", "TVOL08", "PIT8"),
    "total_gas": ("TG", "TOTAL_GAS", "TOTALGAS", "GASA"),
    "c1": ("C1", "METHANE", "METHA"),
    "c2": ("C2", "ETHANE", "ETHA"),
    "c3": ("C3", "PROPANE", "PROPA"),
    "c4": ("C4", "BUTANE"),
    "c5": ("C5", "PENTANE"),
    "ic4": ("IC4", "IBUTANE", "IBUTA"),
    "nc4": ("NC4", "NBUTANE", "NBUTA"),
    "ic5": ("IC5", "IPENTANE", "IPENTA"),
    "nc5": ("NC5", "NPENTANE", "NPENTA"),
    "co2": ("CO2", "CO2A"),
    "h2s": ("MS_H2S", "H2S"),
}


_DEPTH_MOTION = (
    "hole_depth",
    "bit_depth",
    "bit_distance",
    "block_position",
    "block_speed",
    "rop",
    "lag_time",
)
_MECHANICS = ("hook_load", "string_weight", "wob", "rpm", "torque")
_HYDRAULICS = (
    "spp",
    "pump_1",
    "pump_2",
    "pump_3",
    "flow_in",
    "flow_out",
    "mud_density_in",
    "mud_density_out",
    "mud_temp_in",
    "mud_temp_out",
)
_PITS = (
    "pit_total",
    "pit_1",
    "pit_2",
    "pit_3",
    "pit_4",
    "pit_5",
    "pit_6",
    "pit_7",
    "pit_8",
)
_GAS = (
    "total_gas",
    "c1",
    "c2",
    "c3",
    "c4",
    "c5",
    "ic4",
    "nc4",
    "ic5",
    "nc5",
    "co2",
    "h2s",
)


_LIVE_FORMS: tuple[Wits0LiveFormDefinition, ...] = (
    Wits0LiveFormDefinition(
        UNIVERSAL_LIVE_FORM_ID,
        "Универсальная WITS",
        "Әмбебап WITS",
        "Universal WITS",
        _DEPTH_MOTION + _MECHANICS + _HYDRAULICS + _PITS + _GAS,
    ),
    Wits0LiveFormDefinition(
        "drilling",
        "Бурение и механика",
        "Бұрғылау және механика",
        "Drilling and mechanics",
        _DEPTH_MOTION + _MECHANICS,
    ),
    Wits0LiveFormDefinition(
        "hydraulics",
        "Насосы и раствор",
        "Сорғылар және ерітінді",
        "Pumps and mud",
        _HYDRAULICS,
    ),
    Wits0LiveFormDefinition(
        "pits",
        "Ёмкости и объёмы",
        "Ыдыстар және көлемдер",
        "Pits and volumes",
        _PITS,
    ),
    Wits0LiveFormDefinition(
        "gas",
        "Газ C1–C5",
        "C1–C5 газы",
        "Gas C1–C5",
        _GAS,
    ),
    Wits0LiveFormDefinition(
        CUSTOM_LIVE_FORM_ID,
        "Пользовательская",
        "Пайдаланушы",
        "Custom",
        (),
        custom=True,
    ),
)


_ALIAS_TO_CHANNEL: dict[str, str] = {}
for _channel_key, _aliases in _CHANNEL_ALIASES.items():
    for _alias in _aliases:
        _normalized = normalize_sensor_key(_alias)
        if _normalized:
            _ALIAS_TO_CHANNEL.setdefault(_normalized, _channel_key)

_UNIVERSAL_PRIORITY = {
    channel_key: index
    for index, channel_key in enumerate(
        next(
            item.channel_keys
            for item in _LIVE_FORMS
            if item.form_id == UNIVERSAL_LIVE_FORM_ID
        )
    )
}


def live_form_definitions() -> tuple[Wits0LiveFormDefinition, ...]:
    return _LIVE_FORMS


def live_form(form_id: str) -> Wits0LiveFormDefinition:
    for definition in _LIVE_FORMS:
        if definition.form_id == form_id:
            return definition
    raise KeyError(f"Unknown WITS0 live form: {form_id}")


def live_channel_key(*mnemonics: str | None) -> str | None:
    """Resolve the first known semantic live-channel key for supplied mnemonics."""

    for mnemonic in mnemonics:
        if not mnemonic:
            continue
        channel_key = _ALIAS_TO_CHANNEL.get(normalize_sensor_key(mnemonic))
        if channel_key is not None:
            return channel_key
    return None


def live_curve_priority(*mnemonics: str | None) -> int:
    channel_key = live_channel_key(*mnemonics)
    if channel_key is None:
        return len(_UNIVERSAL_PRIORITY) + 1
    return _UNIVERSAL_PRIORITY[channel_key]


def select_live_curve_ids(
    form_id: str,
    curves: Iterable[tuple[str, str | None, str | None]],
) -> tuple[str, ...]:
    """Select curve IDs for one live form while preserving dataset order."""

    definition = live_form(form_id)
    if definition.custom:
        return ()
    wanted = set(definition.channel_keys)
    selected: list[str] = []
    seen: set[str] = set()
    for curve_id, canonical_mnemonic, original_mnemonic in curves:
        channel_key = live_channel_key(canonical_mnemonic, original_mnemonic)
        if channel_key not in wanted or curve_id in seen:
            continue
        selected.append(curve_id)
        seen.add(curve_id)
    return tuple(selected)
