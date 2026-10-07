"""Renderer-neutral gas-context labels shared by charts and client tables."""
from __future__ import annotations

from geoworkbench.domain.gas_context_events import GasContextEventType, InterpretationImpact
from geoworkbench.services.localization import AppLanguage


_LABELS = {
    GasContextEventType.BACKGROUND: ("BG", "Фоновый газ", "Фондық газ", "Background gas"),
    GasContextEventType.FORMATION_SHOW: ("FORM", "Пластовое газопроявление", "Қабаттық газ көрінісі", "Formation show"),
    GasContextEventType.CONNECTION_GAS: ("CONN", "Газ соединения", "Қосылу газы", "Connection gas"),
    GasContextEventType.TRIP_GAS: ("TRIP", "Газ СПО", "Көтеріп-түсіру газы", "Trip gas"),
    GasContextEventType.SWAB_GAS: ("SWAB", "Газ свабирования", "Свабтау газы", "Swab gas"),
    GasContextEventType.CIRCULATED_GAS: ("CIRC", "Циркулирующий газ", "Айналым газы", "Circulated gas"),
    GasContextEventType.RECYCLED_GAS: ("REC", "Рециркулированный газ", "Қайта айналған газ", "Recycled gas"),
    GasContextEventType.CHROMATOGRAPH_TEST_GAS: ("CHR", "Тест хроматографа", "Хроматограф сынағы", "Chromatograph test gas"),
    GasContextEventType.GAS_LINE_TEST_GAS: ("LINE", "Тест газовой линии", "Газ желісінің сынағы", "Gas-line test gas"),
    GasContextEventType.LAG_TRACER_GAS: ("LAG", "Газ трассера", "Трассер газы", "Lag tracer gas"),
    GasContextEventType.CALIBRATION_GAS: ("CAL", "Калибровочный газ", "Калибрлеу газы", "Calibration gas"),
    GasContextEventType.ELEVATED_UNCLASSIFIED: ("REV", "Повышенный газ: уточнить", "Жоғары газ: нақтылау", "Elevated unclassified gas"),
    GasContextEventType.OTHER_TECHNOLOGICAL: ("TECH", "Другой технологический газ", "Басқа технологиялық газ", "Other technological gas"),
}
_IMPACT_LABELS = {
    InterpretationImpact.EXCLUDE_GEOLOGICAL: ("Исключить из геологической интерпретации", "Геологиялық интерпретациядан алып тастау", "Exclude from geological interpretation"),
    InterpretationImpact.TECHNOLOGICAL_GAS: ("Технологический газ", "Технологиялық газ", "Technological gas"),
    InterpretationImpact.FORMATION_GAS: ("Пластовый газ", "Қабат газы", "Formation gas"),
    InterpretationImpact.REVIEW_REQUIRED: ("Требуется проверка", "Тексеру қажет", "Review required"),
}


def gas_context_event_label(event_type: GasContextEventType, language: AppLanguage) -> str:
    return _LABELS[event_type][1 + list(AppLanguage).index(language)]


def gas_context_event_code(event_type: GasContextEventType) -> str:
    return _LABELS[event_type][0]


def gas_context_type_text(event_type: GasContextEventType, language: AppLanguage) -> str:
    return f"{gas_context_event_code(event_type)} — {gas_context_event_label(event_type, language)}"


def gas_context_impact_label(impact: InterpretationImpact, language: AppLanguage) -> str:
    return _IMPACT_LABELS[impact][list(AppLanguage).index(language)]


def gas_context_identity_label(language: AppLanguage) -> str:
    return {AppLanguage.RU: "ID события", AppLanguage.KK: "Оқиға ID", AppLanguage.EN: "Event ID"}[language]
