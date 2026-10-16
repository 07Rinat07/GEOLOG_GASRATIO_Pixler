"""Qualitative profile cues without introducing universal oil/gas cutoffs."""
from collections.abc import Sequence
from math import isfinite

from geoworkbench.services.fluid_phase_contract import FluidPhaseContract
from geoworkbench.services.localization import AppLanguage


def pixler_profile_trend(values: Sequence[float]) -> str:
    """Describe C1/C3 through C1/C5 geometry, not productivity or a proven phase."""
    if len(values) != 4 or any(not isfinite(value) or value <= 0 for value in values):
        return "unknown"
    tail = values[1:]
    if tail[0] < tail[1] < tail[2]:
        return "rising"
    if tail[0] > tail[1] > tail[2]:
        return "falling"
    if tail[0] == tail[1] == tail[2]:
        return "flat"
    return "mixed"


def pixler_profile_caption(
    phase: FluidPhaseContract, trend: str, language: AppLanguage,
) -> tuple[str, str]:
    phases = {
        AppLanguage.RU: ("газовая фаза", "жидкая УВ-фаза", "признаки лёгкой нефти",
                         "жидкая / конденсат", "фаза не определена"),
        AppLanguage.KK: ("газ фазасы", "сұйық КС фазасы", "жеңіл мұнай белгілері",
                         "сұйық / конденсат", "фаза анықталмаған"),
        AppLanguage.EN: ("gas phase", "liquid HC phase", "light oil indications",
                         "liquid / condensate", "phase undetermined"),
    }[language]
    phase_index = {FluidPhaseContract.GAS: 0, FluidPhaseContract.LIQUID: 1,
                   FluidPhaseContract.LIGHT_OIL: 2, FluidPhaseContract.LIQUID_OR_CONDENSATE: 3,
                   FluidPhaseContract.INDETERMINATE: 4}[phase]
    trends = {
        AppLanguage.RU: {"rising": "↑ C1/C3–C1/C5 растут", "falling": "↓ C1/C3–C1/C5 снижаются",
                         "flat": "→ отношения стабильны", "mixed": "↕ смешанный тренд",
                         "unknown": "тренд не определён"},
        AppLanguage.KK: {"rising": "↑ C1/C3–C1/C5 өседі", "falling": "↓ C1/C3–C1/C5 төмендейді",
                         "flat": "→ қатынастар тұрақты", "mixed": "↕ аралас тренд",
                         "unknown": "тренд анықталмаған"},
        AppLanguage.EN: {"rising": "↑ C1/C3–C1/C5 rise", "falling": "↓ C1/C3–C1/C5 fall",
                         "flat": "→ stable ratios", "mixed": "↕ mixed trend",
                         "unknown": "trend undetermined"},
    }[language]
    return phases[phase_index], trends.get(trend, trends["unknown"])


def pixler_visual_tendency(trend: str, language: AppLanguage) -> str:
    """Label a qualitative shape cue separately from interval phase evidence."""
    labels = {
        AppLanguage.RU: {
            "rising": "↑ газовая тенденция по форме",
            "falling": "↓ жидкая УВ-тенденция по форме",
            "mixed": "↕ переходный / смешанный профиль",
            "flat": "→ стабильные отношения",
            "unknown": "тенденция не определена",
        },
        AppLanguage.KK: {
            "rising": "↑ пішіні бойынша газ үрдісі",
            "falling": "↓ пішіні бойынша сұйық КС үрдісі",
            "mixed": "↕ өтпелі / аралас профиль",
            "flat": "→ тұрақты қатынастар",
            "unknown": "үрдіс анықталмаған",
        },
        AppLanguage.EN: {
            "rising": "↑ gas tendency by profile shape",
            "falling": "↓ liquid HC tendency by shape",
            "mixed": "↕ transitional / mixed profile",
            "flat": "→ stable ratios",
            "unknown": "tendency undetermined",
        },
    }
    return labels[language].get(trend, labels[language]["unknown"])
