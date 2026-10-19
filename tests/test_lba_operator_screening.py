"""LBA operator examples must remain provisional, with QC and provenance."""

import pytest

from geoworkbench.services.lba_operator_screening import (
    LbaFluidContext,
    LbaScreeningControls,
    LbaScreeningStatus,
    screen_lba_operator_pattern,
)


@pytest.mark.parametrize(
    ("score", "colour", "type_id", "group", "expected"),
    (
        (1, "БГ", "ЛБ", 1, {LbaFluidContext.GAS_ASSOCIATED}),
        (2, "БГ", "ЛБ", 1, {
            LbaFluidContext.GAS_ASSOCIATED,
            LbaFluidContext.GAS_CONDENSATE,
            LbaFluidContext.LIGHT_OIL,
        }),
        (2, "БЖ", "МБ", 2, {
            LbaFluidContext.LIGHT_OIL, LbaFluidContext.GAS_CONDENSATE,
        }),
        (3, "БЖ", "МБ", 2, {
            LbaFluidContext.LIGHT_OIL, LbaFluidContext.GAS_CONDENSATE,
        }),
        (3, "ГЖ", "МБ", 2, {
            LbaFluidContext.LIGHT_OIL, LbaFluidContext.GAS_CONDENSATE,
        }),
        (3, "ОЖ", "МСБ", 3, {
            LbaFluidContext.OIL_OR_RESIDUAL_BITUMEN,
        }),
    ),
)
def test_operator_examples_are_hypotheses_not_saturation(
    score: int, colour: str, type_id: str, group: int,
    expected: set[LbaFluidContext],
) -> None:
    result = screen_lba_operator_pattern(
        group=group, type_id=type_id, colour=f"{colour} — цвет",
        residual_ring_score=score,
    )
    assert result.status is LbaScreeningStatus.OPERATOR_HYPOTHESIS
    assert set(result.candidate_contexts) == expected
    assert result.pattern_id == f"{score}-{colour}-{type_id}"
    assert result.warnings == (
        "sample_depth_or_lag_unverified",
        "mud_solvent_blank_unknown",
        "drilling_additives_unknown",
        "coal_organic_matter_unknown",
    )
    assert not result.confirms_reservoir_phase
    assert not result.confirms_hydrocarbon_saturation


@pytest.mark.parametrize("issue", ("drilling", "coal", "blank"))
def test_confounded_example_suppresses_fluid_hypotheses(issue: str) -> None:
    controls = {
        "drilling": LbaScreeningControls(drilling_fluid_additives_present=True),
        "coal": LbaScreeningControls(coal_or_organic_matter_present=True),
        "blank": LbaScreeningControls(mud_or_solvent_blank_fluoresces=True),
    }[issue]
    result = screen_lba_operator_pattern(
        group=1, type_id="ЛБ", colour="БГ", residual_ring_score=2,
        controls=controls,
    )
    assert result.status is LbaScreeningStatus.CONTAMINATION_REVIEW
    assert result.candidate_contexts == ()


def test_verified_blank_lag_and_absent_confounders_only_remove_qc_warnings() -> None:
    result = screen_lba_operator_pattern(
        group=2, type_id="МБ", colour="БЖ", residual_ring_score=3,
        controls=LbaScreeningControls(
            depth_and_lag_verified=True, mud_or_solvent_blank_fluoresces=False,
            drilling_fluid_additives_present=False,
            coal_or_organic_matter_present=False,
        ),
    )
    assert result.status is LbaScreeningStatus.OPERATOR_HYPOTHESIS
    assert result.warnings == ()
    assert not result.confirms_reservoir_phase


@pytest.mark.parametrize("score", (0, 6, True, 2.5))
def test_invalid_residue_score_never_matches(score: object) -> None:
    result = screen_lba_operator_pattern(
        group=1, type_id="ЛБ", colour="БГ",
        residual_ring_score=score,  # type: ignore[arg-type]
    )
    assert result.status is LbaScreeningStatus.INVALID_OBSERVATION
    assert result.candidate_contexts == ()


def test_group_or_colour_conflict_blocks_operator_rule() -> None:
    result = screen_lba_operator_pattern(
        group=1, type_id="ЛБ", colour="ОЖ", residual_ring_score=3,
    )
    assert result.status is LbaScreeningStatus.INVALID_OBSERVATION
    assert result.candidate_contexts == ()


def test_absent_or_ambiguous_group_does_not_create_hypotheses() -> None:
    no_group = screen_lba_operator_pattern(
        group=None, type_id=None, colour="СК", residual_ring_score=3,
    )
    missing_score = screen_lba_operator_pattern(
        group=1, type_id="ЛБ", colour="БГ", residual_ring_score=None,
    )
    assert no_group.status is LbaScreeningStatus.INCOMPLETE_OBSERVATION
    assert missing_score.status is LbaScreeningStatus.INCOMPLETE_OBSERVATION


def test_unknown_valid_colour_score_combination_is_not_negative_lba() -> None:
    result = screen_lba_operator_pattern(
        group=3, type_id="МСБ", colour="Ж", residual_ring_score=4,
    )
    assert result.status is LbaScreeningStatus.UNCATALOGUED_PATTERN
    assert result.candidate_contexts == ()
    assert result.pattern_id == "4-Ж-МСБ"


def test_invalid_qc_flag_rejected_explicitly() -> None:
    with pytest.raises(ValueError, match="QC control"):
        screen_lba_operator_pattern(
            group=1, type_id="ЛБ", colour="БГ", residual_ring_score=2,
            controls=LbaScreeningControls(
                coal_or_organic_matter_present="yes",  # type: ignore[arg-type]
            ),
        )

@pytest.mark.parametrize(
    ("group", "type_id"),
    ((6, "ЛБ"), (-1, "ЛБ"), (True, "ЛБ"), (1, "unknown type")),
)
def test_invalid_operator_group_or_type_cannot_be_salvaged_by_other_field(
    group: object, type_id: str,
) -> None:
    result = screen_lba_operator_pattern(
        group=group,  # type: ignore[arg-type]
        type_id=type_id, colour="БГ", residual_ring_score=1,
    )
    assert result.status is LbaScreeningStatus.INVALID_OBSERVATION
    assert result.candidate_contexts == ()
