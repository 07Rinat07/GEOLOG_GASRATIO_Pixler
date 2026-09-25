from __future__ import annotations

from geoworkbench.services.localization import AppLanguage
from geoworkbench.services.wits0_gas_context import (
    Wits0GasContextAssessment,
    Wits0GasOriginKind,
)
from geoworkbench.services.wits0_gas_context_presentation import present_resolved_gas_context
from geoworkbench.services.wits0_manual_gas_context import (
    Wits0GasContextAxis,
    Wits0GasContextResolutionSource,
    Wits0ManualGasContextInterval,
    resolve_effective_gas_context,
    resolve_manual_gas_context,
)


def test_manual_test_interval_overrides_overlapping_formation_show() -> None:
    intervals = (
        Wits0ManualGasContextInterval(
            interval_id="formation",
            kind=Wits0GasOriginKind.FORMATION_SHOW,
            axis=Wits0GasContextAxis.DEPTH,
            start=2500.0,
            end=2510.0,
        ),
        Wits0ManualGasContextInterval(
            interval_id="gc-test",
            kind=Wits0GasOriginKind.CHROMATOGRAPH_TEST_GAS,
            axis=Wits0GasContextAxis.DEPTH,
            start=2504.0,
            end=2505.0,
            event_value=1.0,
            event_unit="%",
            comment="Certified C1-C5 calibration mix",
        ),
    )

    resolved = resolve_manual_gas_context(
        intervals,
        axis=Wits0GasContextAxis.DEPTH,
        value=2504.5,
    )

    assert resolved is not None
    assert resolved.kind is Wits0GasOriginKind.CHROMATOGRAPH_TEST_GAS
    assert resolved.excludes_formation_interpretation is True


def test_unconfirmed_manual_interval_is_ignored() -> None:
    interval = Wits0ManualGasContextInterval(
        interval_id="draft-trip",
        kind=Wits0GasOriginKind.TRIP_GAS,
        axis=Wits0GasContextAxis.ELAPSED_TIME,
        start=100.0,
        end=200.0,
        confirmed=False,
    )

    assert (
        resolve_manual_gas_context(
            (interval,),
            axis=Wits0GasContextAxis.ELAPSED_TIME,
            value=150.0,
        )
        is None
    )


def _automatic_formation_show() -> Wits0GasContextAssessment:
    return Wits0GasContextAssessment(
        kind=Wits0GasOriginKind.FORMATION_SHOW,
        total_gas=25.0,
        background=10.0,
        threshold=11.0,
        ratio_to_background=2.5,
        confidence=0.84,
        reason_codes=("stable_drilling_context", "gas_above_background"),
    )


def test_confirmed_manual_test_context_overrides_automatic_formation_show() -> None:
    automatic = _automatic_formation_show()
    interval = Wits0ManualGasContextInterval(
        interval_id="manual-gc-test",
        kind=Wits0GasOriginKind.CHROMATOGRAPH_TEST_GAS,
        axis=Wits0GasContextAxis.DEPTH,
        start=2504.0,
        end=2505.0,
        confirmed=True,
    )

    resolved = resolve_effective_gas_context(
        automatic,
        (interval,),
        axis=Wits0GasContextAxis.DEPTH,
        value=2504.5,
    )

    assert resolved.kind is Wits0GasOriginKind.CHROMATOGRAPH_TEST_GAS
    assert resolved.source is Wits0GasContextResolutionSource.MANUAL
    assert resolved.manual_interval_id == "manual-gc-test"
    assert resolved.excludes_formation_interpretation is True
    assert resolved.automatic is automatic


def test_unconfirmed_manual_context_does_not_override_automatic_result() -> None:
    automatic = _automatic_formation_show()
    interval = Wits0ManualGasContextInterval(
        interval_id="draft-trip",
        kind=Wits0GasOriginKind.TRIP_GAS,
        axis=Wits0GasContextAxis.DEPTH,
        start=2500.0,
        end=2510.0,
        confirmed=False,
    )

    resolved = resolve_effective_gas_context(
        automatic,
        (interval,),
        axis=Wits0GasContextAxis.DEPTH,
        value=2505.0,
    )

    assert resolved.kind is Wits0GasOriginKind.FORMATION_SHOW
    assert resolved.source is Wits0GasContextResolutionSource.AUTOMATIC
    assert resolved.manual_interval_id is None
    assert resolved.excludes_formation_interpretation is False


def test_manual_operational_context_precedence_is_preserved_for_overlap() -> None:
    automatic = _automatic_formation_show()
    intervals = (
        Wits0ManualGasContextInterval(
            interval_id="manual-formation",
            kind=Wits0GasOriginKind.FORMATION_SHOW,
            axis=Wits0GasContextAxis.DEPTH,
            start=2500.0,
            end=2510.0,
        ),
        Wits0ManualGasContextInterval(
            interval_id="manual-trip",
            kind=Wits0GasOriginKind.TRIP_GAS,
            axis=Wits0GasContextAxis.DEPTH,
            start=2502.0,
            end=2508.0,
        ),
    )

    resolved = resolve_effective_gas_context(
        automatic,
        intervals,
        axis=Wits0GasContextAxis.DEPTH,
        value=2505.0,
    )

    assert resolved.kind is Wits0GasOriginKind.TRIP_GAS
    assert resolved.manual_interval_id == "manual-trip"
    assert resolved.excludes_formation_interpretation is True


def test_resolved_gas_context_presentation_preserves_effective_and_automatic_audit() -> None:
    automatic = _automatic_formation_show()
    manual = Wits0ManualGasContextInterval(
        interval_id="gc-test-42",
        kind=Wits0GasOriginKind.CHROMATOGRAPH_TEST_GAS,
        axis=Wits0GasContextAxis.DEPTH,
        start=2504.0,
        end=2505.0,
    )
    resolved = resolve_effective_gas_context(
        automatic,
        (manual,),
        axis=Wits0GasContextAxis.DEPTH,
        value=2504.5,
    )

    ru = present_resolved_gas_context(resolved, AppLanguage.RU)
    en = present_resolved_gas_context(resolved, AppLanguage.EN)

    assert ru.effective_label == "Тестовый газ хроматографа"
    assert ru.automatic_label == "Пластовое газопроявление"
    assert ru.source_label == "Подтверждено оператором"
    assert "gc-test-42" in ru.audit_text
    assert ru.excludes_formation_interpretation is True

    assert en.effective_label == "Chromatograph test gas"
    assert en.automatic_label == "Formation gas show"
    assert en.source_label == "Operator confirmed"
    assert "gc-test-42" in en.audit_text


def test_automatic_gas_context_presentation_has_no_manual_interval() -> None:
    automatic = _automatic_formation_show()
    resolved = resolve_effective_gas_context(
        automatic,
        (),
        axis=Wits0GasContextAxis.DEPTH,
        value=2504.5,
    )

    presentation = present_resolved_gas_context(resolved, AppLanguage.KK)

    assert presentation.manual_interval_id is None
    assert presentation.source_label == "Автоматты"
    assert presentation.effective_label == presentation.automatic_label
