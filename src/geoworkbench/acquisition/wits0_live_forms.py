from __future__ import annotations

from collections.abc import Iterable
from dataclasses import asdict, dataclass
import json
import math
from typing import Protocol

from geoworkbench.catalogs.sensors import normalize_sensor_key
from geoworkbench.services.wits0_alarms import AlarmLimits


CUSTOM_LIVE_FORM_ID = "custom"
UNIVERSAL_LIVE_FORM_ID = "universal"
WITS0_LIVE_FORM_STATE_SCHEMA_VERSION = 4


@dataclass(frozen=True, slots=True)
class Wits0LiveFormDefinition:
    """A named projection of engineering channels for the WITS0 live workspace."""

    form_id: str
    title_ru: str
    title_kk: str
    title_en: str
    channel_keys: tuple[str, ...]
    custom: bool = False
    description_ru: str = ""
    description_kk: str = ""
    description_en: str = ""

    def title(self, language: object) -> str:
        code = str(getattr(language, "value", language)).strip().casefold()
        if code == "kk":
            return self.title_kk
        if code == "en":
            return self.title_en
        return self.title_ru

    def description(self, language: object) -> str:
        code = str(getattr(language, "value", language)).strip().casefold()
        if code == "kk":
            return self.description_kk
        if code == "en":
            return self.description_en
        return self.description_ru


@dataclass(frozen=True, slots=True)
class Wits0SavedAlarmRule:
    """Persisted threshold policy for one WITS live channel."""

    mnemonic: str
    minimum: float | None = None
    maximum: float | None = None
    hysteresis: float = 0.0
    debounce_samples: int = 1
    visual_enabled: bool = True
    audio_enabled: bool = False

    def __post_init__(self) -> None:
        if not isinstance(self.mnemonic, str) or not self.mnemonic.strip():
            raise ValueError("alarm mnemonic must be a non-empty string")
        if not isinstance(self.visual_enabled, bool) or not isinstance(
            self.audio_enabled, bool
        ):
            raise ValueError("alarm visual/audio flags must be booleans")
        AlarmLimits(
            minimum=self.minimum,
            maximum=self.maximum,
            hysteresis=self.hysteresis,
            debounce_samples=self.debounce_samples,
        )


@dataclass(frozen=True, slots=True)
class Wits0SavedLiveFormState:
    """Persisted operator overrides for one named WITS live form."""

    form_id: str
    selected_mnemonics: tuple[str, ...] = ()
    axis_mode: str = "auto"
    auto_follow: bool = True
    follow_span: float = 600.0
    max_points: int = 2_000
    sidebar_visible: bool = True
    panel_order: tuple[str, ...] = ()
    hidden_panel_ids: tuple[str, ...] = ()
    panel_x_ranges: tuple[tuple[str, float, float], ...] = ()
    alarm_rules: tuple[Wits0SavedAlarmRule, ...] = ()
    schema_version: int = WITS0_LIVE_FORM_STATE_SCHEMA_VERSION

    def __post_init__(self) -> None:
        if not self.form_id.strip():
            raise ValueError("form_id must not be empty")
        if self.axis_mode not in {"auto", "time", "depth"}:
            raise ValueError("Unsupported WITS live-form axis mode")
        if not isinstance(self.auto_follow, bool) or not isinstance(self.sidebar_visible, bool):
            raise ValueError("WITS live-form flags must be booleans")
        if not 0.1 <= float(self.follow_span) <= 100_000.0:
            raise ValueError("follow_span is outside supported range")
        if isinstance(self.max_points, bool) or not 100 <= self.max_points <= 20_000:
            raise ValueError("max_points is outside supported range")
        if self.schema_version != WITS0_LIVE_FORM_STATE_SCHEMA_VERSION:
            raise ValueError("Unsupported WITS live-form settings schema")
        if not all(
            isinstance(item, str) and item.strip()
            for item in self.selected_mnemonics
        ):
            raise ValueError("selected_mnemonics must contain non-empty strings")
        for field_name, items in (
            ("panel_order", self.panel_order),
            ("hidden_panel_ids", self.hidden_panel_ids),
        ):
            if not all(isinstance(item, str) and item.strip() for item in items):
                raise ValueError(f"{field_name} must contain non-empty strings")
            if len(set(items)) != len(items):
                raise ValueError(f"{field_name} must not contain duplicates")
        scale_keys: list[str] = []
        for entry in self.panel_x_ranges:
            if not isinstance(entry, tuple) or len(entry) != 3:
                raise ValueError("panel_x_ranges entries must have key/min/max")
            scale_key, minimum, maximum = entry
            if not isinstance(scale_key, str) or not scale_key.strip():
                raise ValueError("panel_x_ranges keys must be non-empty strings")
            if (
                isinstance(minimum, bool)
                or isinstance(maximum, bool)
                or not math.isfinite(float(minimum))
                or not math.isfinite(float(maximum))
                or float(minimum) >= float(maximum)
            ):
                raise ValueError("panel_x_ranges require finite min < max")
            scale_keys.append(scale_key)
        if len(set(scale_keys)) != len(scale_keys):
            raise ValueError("panel_x_ranges keys must not contain duplicates")
        if not all(isinstance(rule, Wits0SavedAlarmRule) for rule in self.alarm_rules):
            raise ValueError("alarm_rules must contain saved alarm rules")
        alarm_keys = [normalize_sensor_key(rule.mnemonic) for rule in self.alarm_rules]
        if any(not key for key in alarm_keys):
            raise ValueError("alarm_rules must contain valid mnemonics")
        if len(set(alarm_keys)) != len(alarm_keys):
            raise ValueError("alarm_rules mnemonics must not contain duplicates")


def _optional_float(value: object) -> float | None:
    if value is None:
        return None
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError("alarm limit must be numeric or null")
    return float(value)


class _SettingsLike(Protocol):
    def value(self, key: str, default: object = None) -> object: ...
    def setValue(self, key: str, value: object) -> None: ...
    def remove(self, key: str) -> None: ...
    def sync(self) -> None: ...


class Wits0LiveFormSettings:
    """QSettings-compatible persistence for editable operator forms."""

    def __init__(
        self,
        settings: _SettingsLike,
        *,
        namespace: str = "wits0/live-forms",
    ) -> None:
        self.settings = settings
        self.namespace = namespace.rstrip("/")

    def load(self, form_id: str) -> Wits0SavedLiveFormState | None:
        raw = self.settings.value(self._key(form_id), "")
        if not str(raw).strip():
            return None
        try:
            payload = json.loads(str(raw))
            if not isinstance(payload, dict):
                return None
            schema_version = int(payload.get("schema_version", 1))
            if schema_version not in {
                1,
                2,
                3,
                WITS0_LIVE_FORM_STATE_SCHEMA_VERSION,
            }:
                return None
            selected = payload.get("selected_mnemonics", [])
            panel_order = payload.get("panel_order", [])
            hidden_panel_ids = payload.get("hidden_panel_ids", [])
            panel_x_ranges = payload.get("panel_x_ranges", [])
            alarm_rules = payload.get("alarm_rules", [])
            for values in (selected, panel_order, hidden_panel_ids):
                if not isinstance(values, list) or not all(
                    isinstance(item, str) for item in values
                ):
                    return None
            if not isinstance(panel_x_ranges, list):
                return None
            parsed_ranges: list[tuple[str, float, float]] = []
            for entry in panel_x_ranges:
                if not isinstance(entry, list) or len(entry) != 3:
                    return None
                scale_key, minimum, maximum = entry
                if not isinstance(scale_key, str):
                    return None
                parsed_ranges.append(
                    (scale_key, float(minimum), float(maximum))
                )
            if not isinstance(alarm_rules, list):
                return None
            parsed_alarm_rules: list[Wits0SavedAlarmRule] = []
            if schema_version >= 4:
                for entry in alarm_rules:
                    if not isinstance(entry, dict):
                        return None
                    mnemonic = entry.get("mnemonic")
                    if not isinstance(mnemonic, str):
                        return None
                    parsed_alarm_rules.append(
                        Wits0SavedAlarmRule(
                            mnemonic=mnemonic,
                            minimum=_optional_float(entry.get("minimum")),
                            maximum=_optional_float(entry.get("maximum")),
                            hysteresis=float(entry.get("hysteresis", 0.0)),
                            debounce_samples=int(entry.get("debounce_samples", 1)),
                            visual_enabled=entry.get("visual_enabled", True),
                            audio_enabled=entry.get("audio_enabled", False),
                        )
                    )
            return Wits0SavedLiveFormState(
                form_id=str(payload.get("form_id", form_id)),
                selected_mnemonics=tuple(selected),
                axis_mode=str(payload.get("axis_mode", "auto")),
                auto_follow=payload.get("auto_follow", True),
                follow_span=float(payload.get("follow_span", 600.0)),
                max_points=int(payload.get("max_points", 2_000)),
                sidebar_visible=payload.get("sidebar_visible", True),
                panel_order=(
                    tuple(panel_order)
                    if schema_version >= 2
                    else ()
                ),
                hidden_panel_ids=(
                    tuple(hidden_panel_ids)
                    if schema_version >= 2
                    else ()
                ),
                panel_x_ranges=(
                    tuple(parsed_ranges)
                    if schema_version >= 3
                    else ()
                ),
                alarm_rules=(
                    tuple(parsed_alarm_rules)
                    if schema_version >= 4
                    else ()
                ),
                schema_version=WITS0_LIVE_FORM_STATE_SCHEMA_VERSION,
            )
        except (TypeError, ValueError, json.JSONDecodeError):
            return None

    def save(self, state: Wits0SavedLiveFormState) -> None:
        self.settings.setValue(
            self._key(state.form_id),
            json.dumps(asdict(state), ensure_ascii=False, sort_keys=True),
        )
        self.settings.sync()

    def reset(self, form_id: str) -> None:
        self.settings.remove(self._key(form_id))
        self.settings.sync()

    def _key(self, form_id: str) -> str:
        safe = "".join(
            character if character.isalnum() or character in "-_."
            else "_"
            for character in form_id
        )
        return f"{self.namespace}/{safe or CUSTOM_LIVE_FORM_ID}"


@dataclass(frozen=True, slots=True)
class Wits0LivePanelDefinition:
    """One operator-dashboard panel with engineering-compatible channels."""

    panel_id: str
    title_ru: str
    title_kk: str
    title_en: str
    channel_keys: tuple[str, ...]

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




_LIVE_PANELS: tuple[Wits0LivePanelDefinition, ...] = (
    Wits0LivePanelDefinition(
        "depth",
        "Глубины и положение",
        "Тереңдік және орын",
        "Depth and position",
        ("hole_depth", "bit_depth", "bit_distance", "block_position"),
    ),
    Wits0LivePanelDefinition(
        "rate",
        "Скорость и проходка",
        "Жылдамдық және өту",
        "Rate and ROP",
        ("block_speed", "rop"),
    ),
    Wits0LivePanelDefinition(
        "lag",
        "Отставание",
        "Кешігу",
        "Lag",
        ("lag_time",),
    ),
    Wits0LivePanelDefinition(
        "load",
        "Нагрузки",
        "Жүктемелер",
        "Loads",
        ("hook_load", "string_weight", "wob"),
    ),
    Wits0LivePanelDefinition(
        "rotation",
        "Обороты",
        "Айналым",
        "Rotation",
        ("rpm",),
    ),
    Wits0LivePanelDefinition(
        "torque",
        "Крутящий момент",
        "Айналу моменті",
        "Torque",
        ("torque",),
    ),
    Wits0LivePanelDefinition(
        "pressure",
        "Давление",
        "Қысым",
        "Pressure",
        ("spp",),
    ),
    Wits0LivePanelDefinition(
        "pumps",
        "Насосы",
        "Сорғылар",
        "Pumps",
        ("pump_1", "pump_2", "pump_3"),
    ),
    Wits0LivePanelDefinition(
        "flow",
        "Расход",
        "Шығын",
        "Flow",
        ("flow_in", "flow_out"),
    ),
    Wits0LivePanelDefinition(
        "mud_density",
        "Плотность раствора",
        "Ерітінді тығыздығы",
        "Mud density",
        ("mud_density_in", "mud_density_out"),
    ),
    Wits0LivePanelDefinition(
        "mud_temperature",
        "Температура раствора",
        "Ерітінді температурасы",
        "Mud temperature",
        ("mud_temp_in", "mud_temp_out"),
    ),
    Wits0LivePanelDefinition(
        "pits",
        "Ёмкости",
        "Ыдыстар",
        "Pits",
        _PITS,
    ),
    Wits0LivePanelDefinition(
        "gas_total",
        "Общий газ",
        "Жалпы газ",
        "Total gas",
        ("total_gas",),
    ),
    Wits0LivePanelDefinition(
        "gas_components",
        "Газовые компоненты",
        "Газ компоненттері",
        "Gas components",
        (
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
        ),
    ),
)

_CHANNEL_TO_PANEL = {
    channel_key: panel.panel_id
    for panel in _LIVE_PANELS
    for channel_key in panel.channel_keys
}


_LIVE_FORMS: tuple[Wits0LiveFormDefinition, ...] = (
    Wits0LiveFormDefinition(
        UNIVERSAL_LIVE_FORM_ID,
        "Универсальная WITS",
        "Әмбебап WITS",
        "Universal WITS",
        _DEPTH_MOTION + _MECHANICS + _HYDRAULICS + _PITS + _GAS,
        description_ru="Общий обзор буровой: глубины, механика, гидравлика, ёмкости и газ.",
        description_kk="Бұрғылау қондырғысының жалпы көрінісі: тереңдік, механика, гидравлика, ыдыстар және газ.",
        description_en="Overall rig view: depth, mechanics, hydraulics, pits and gas.",
    ),
    Wits0LiveFormDefinition(
        "drilling",
        "Бурение и механика",
        "Бұрғылау және механика",
        "Drilling and mechanics",
        _DEPTH_MOTION + _MECHANICS,
        description_ru="Проходка, положение талевого блока, нагрузки, обороты и крутящий момент.",
        description_kk="Өту, таль блогының орны, жүктемелер, айналым және айналу моменті.",
        description_en="ROP, block position, loads, rotary speed and torque.",
    ),
    Wits0LiveFormDefinition(
        "hydraulics",
        "Насосы и раствор",
        "Сорғылар және ерітінді",
        "Pumps and mud",
        _HYDRAULICS,
        description_ru="Давление, насосы, расходы, плотность и температура бурового раствора.",
        description_kk="Қысым, сорғылар, шығын, бұрғылау ерітіндісінің тығыздығы мен температурасы.",
        description_en="Pressure, pumps, flow, mud density and mud temperature.",
    ),
    Wits0LiveFormDefinition(
        "pits",
        "Ёмкости и объёмы",
        "Ыдыстар және көлемдер",
        "Pits and volumes",
        _PITS,
        description_ru="Контроль суммарного и отдельных объёмов ёмкостей.",
        description_kk="Жалпы және жеке ыдыс көлемдерін бақылау.",
        description_en="Monitor total and individual pit volumes.",
    ),
    Wits0LiveFormDefinition(
        "gas",
        "Газ C1–C5",
        "C1–C5 газы",
        "Gas C1–C5",
        _GAS,
        description_ru="Общий газ и компонентный состав C1–C5, CO2 и H2S при наличии каналов.",
        description_kk="Арналар бар болса, жалпы газ және C1–C5, CO2, H2S компоненттері.",
        description_en="Total gas and C1–C5, CO2 and H2S components when available.",
    ),
    Wits0LiveFormDefinition(
        CUSTOM_LIVE_FORM_ID,
        "Пользовательская",
        "Пайдаланушы",
        "Custom",
        (),
        custom=True,
        description_ru="Ручной выбор любых доступных каналов под текущую задачу.",
        description_kk="Ағымдағы міндет үшін қолжетімді арналарды қолмен таңдау.",
        description_en="Manually choose any available channels for the current task.",
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




def live_panel_definitions() -> tuple[Wits0LivePanelDefinition, ...]:
    return _LIVE_PANELS


def live_panel(panel_id: str) -> Wits0LivePanelDefinition:
    for definition in _LIVE_PANELS:
        if definition.panel_id == panel_id:
            return definition
    raise KeyError(f"Unknown WITS0 live panel: {panel_id}")


def live_panel_key(*mnemonics: str | None) -> str | None:
    channel_key = live_channel_key(*mnemonics)
    if channel_key is None:
        return None
    return _CHANNEL_TO_PANEL.get(channel_key)


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
