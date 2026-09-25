from __future__ import annotations

from dataclasses import dataclass

from geoworkbench.services.localization import AppLanguage
from geoworkbench.services.wits0_gas_context_labels import gas_context_label
from geoworkbench.services.wits0_manual_gas_context import (
    Wits0GasContextResolutionSource,
    Wits0ResolvedGasContext,
)


@dataclass(frozen=True, slots=True)
class Wits0GasContextPresentation:
    """Localized presentation boundary shared by operator UI and reports."""

    effective_label: str
    automatic_label: str
    source_label: str
    audit_text: str
    manual_interval_id: str | None
    excludes_formation_interpretation: bool


_SOURCE_LABELS: dict[AppLanguage, dict[Wits0GasContextResolutionSource, str]] = {
    AppLanguage.RU: {
        Wits0GasContextResolutionSource.AUTOMATIC: "Автоматически",
        Wits0GasContextResolutionSource.MANUAL: "Подтверждено оператором",
    },
    AppLanguage.KK: {
        Wits0GasContextResolutionSource.AUTOMATIC: "Автоматты",
        Wits0GasContextResolutionSource.MANUAL: "Оператор растаған",
    },
    AppLanguage.EN: {
        Wits0GasContextResolutionSource.AUTOMATIC: "Automatic",
        Wits0GasContextResolutionSource.MANUAL: "Operator confirmed",
    },
}

_AUDIT_TEMPLATES: dict[AppLanguage, tuple[str, str]] = {
    AppLanguage.RU: (
        "Итог: {effective}. Автоматическая оценка: {automatic}. Источник: {source}.",
        "Итог: {effective}. Автоматическая оценка: {automatic}. "
        "Источник: {source}; manual interval: {interval}.",
    ),
    AppLanguage.KK: (
        "Қорытынды: {effective}. Автоматты бағалау: {automatic}. Дереккөз: {source}.",
        "Қорытынды: {effective}. Автоматты бағалау: {automatic}. "
        "Дереккөз: {source}; manual interval: {interval}.",
    ),
    AppLanguage.EN: (
        "Effective: {effective}. Automatic assessment: {automatic}. Source: {source}.",
        "Effective: {effective}. Automatic assessment: {automatic}. "
        "Source: {source}; manual interval: {interval}.",
    ),
}


def present_resolved_gas_context(
    resolved: Wits0ResolvedGasContext,
    language: AppLanguage,
) -> Wits0GasContextPresentation:
    """Return stable localized text without leaking classification logic into UI/PDF."""

    effective = gas_context_label(resolved.kind, language)
    automatic = gas_context_label(resolved.automatic.kind, language)
    source = _SOURCE_LABELS[language][resolved.source]
    without_manual, with_manual = _AUDIT_TEMPLATES[language]
    if resolved.manual_interval_id is None:
        audit = without_manual.format(
            effective=effective,
            automatic=automatic,
            source=source,
        )
    else:
        audit = with_manual.format(
            effective=effective,
            automatic=automatic,
            source=source,
            interval=resolved.manual_interval_id,
        )
    return Wits0GasContextPresentation(
        effective_label=effective,
        automatic_label=automatic,
        source_label=source,
        audit_text=audit,
        manual_interval_id=resolved.manual_interval_id,
        excludes_formation_interpretation=resolved.excludes_formation_interpretation,
    )


__all__ = [
    "Wits0GasContextPresentation",
    "present_resolved_gas_context",
]
