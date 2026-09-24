from __future__ import annotations

from geoworkbench.services.localization import AppLanguage
from geoworkbench.services.wits0_gas_context import Wits0GasOriginKind


_LABELS: dict[AppLanguage, dict[Wits0GasOriginKind, str]] = {
    AppLanguage.RU: {
        Wits0GasOriginKind.BACKGROUND: "Фоновый газ",
        Wits0GasOriginKind.FORMATION_SHOW: "Пластовое газопроявление",
        Wits0GasOriginKind.CONNECTION_GAS: "Газ наращивания / connection gas",
        Wits0GasOriginKind.TRIP_GAS: "Газ СПО / trip gas",
        Wits0GasOriginKind.CIRCULATED_GAS: "Циркулированный газ",
        Wits0GasOriginKind.RECYCLED_GAS: "Рециркулированный газ",
        Wits0GasOriginKind.CHROMATOGRAPH_TEST_GAS: "Тестовый газ хроматографа",
        Wits0GasOriginKind.GAS_LINE_TEST_GAS: "Тест газовой линии ГТИ",
        Wits0GasOriginKind.LAG_TRACER_GAS: "Газ-трассер / лаг-тест",
        Wits0GasOriginKind.CALIBRATION_GAS: "Калибровочный газ",
        Wits0GasOriginKind.ELEVATED_UNCLASSIFIED: "Повышенный газ — причина не определена",
        Wits0GasOriginKind.INSUFFICIENT_CONTEXT: "Недостаточно контекста",
    },
    AppLanguage.KK: {
        Wits0GasOriginKind.BACKGROUND: "Фондық газ",
        Wits0GasOriginKind.FORMATION_SHOW: "Қабаттық газ көрінісі",
        Wits0GasOriginKind.CONNECTION_GAS: "Құбыр жалғау газы / connection gas",
        Wits0GasOriginKind.TRIP_GAS: "СПО газы / trip gas",
        Wits0GasOriginKind.CIRCULATED_GAS: "Циркуляцияланған газ",
        Wits0GasOriginKind.RECYCLED_GAS: "Қайта циркуляцияланған газ",
        Wits0GasOriginKind.CHROMATOGRAPH_TEST_GAS: "Хроматографтың сынақ газы",
        Wits0GasOriginKind.GAS_LINE_TEST_GAS: "ГТИ газ желісінің сынағы",
        Wits0GasOriginKind.LAG_TRACER_GAS: "Газ-трассер / lag test",
        Wits0GasOriginKind.CALIBRATION_GAS: "Калибрлеу газы",
        Wits0GasOriginKind.ELEVATED_UNCLASSIFIED: "Газ жоғары — себеп анықталмаған",
        Wits0GasOriginKind.INSUFFICIENT_CONTEXT: "Контекст жеткіліксіз",
    },
    AppLanguage.EN: {
        Wits0GasOriginKind.BACKGROUND: "Background gas",
        Wits0GasOriginKind.FORMATION_SHOW: "Formation gas show",
        Wits0GasOriginKind.CONNECTION_GAS: "Connection gas",
        Wits0GasOriginKind.TRIP_GAS: "Trip gas",
        Wits0GasOriginKind.CIRCULATED_GAS: "Circulated gas",
        Wits0GasOriginKind.RECYCLED_GAS: "Recycled gas",
        Wits0GasOriginKind.CHROMATOGRAPH_TEST_GAS: "Chromatograph test gas",
        Wits0GasOriginKind.GAS_LINE_TEST_GAS: "Mud-logging gas-line test",
        Wits0GasOriginKind.LAG_TRACER_GAS: "Lag tracer gas",
        Wits0GasOriginKind.CALIBRATION_GAS: "Calibration gas",
        Wits0GasOriginKind.ELEVATED_UNCLASSIFIED: "Elevated gas — origin unclassified",
        Wits0GasOriginKind.INSUFFICIENT_CONTEXT: "Insufficient context",
    },
}


def gas_context_label(kind: Wits0GasOriginKind, language: AppLanguage) -> str:
    return _LABELS[language][kind]


__all__ = ["gas_context_label"]
