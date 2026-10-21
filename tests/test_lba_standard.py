import pytest

from geoworkbench.services.lba_standard import (
    LBA_STANDARD_GROUPS,
    assess_lba_standard,
    lba_groups_for_color,
    lba_intensity_name,
    describe_lba_assessment,
)
from geoworkbench.services.localization import AppLanguage


def test_lba_reference_contains_five_bitumoid_groups() -> None:
    assert [(item.group, item.code) for item in LBA_STANDARD_GROUPS] == [
        (1, "ЛБ"),
        (2, "МБ"),
        (3, "МСБ"),
        (4, "СБ"),
        (5, "САБ"),
    ]


def test_lba_assessment_keeps_group_and_intensity_as_separate_scales() -> None:
    assessment = assess_lba_standard(
        group=3,
        type_id="МСБ",
        color="ОЖ — оранжево-жёлтый",
        intensity=5,
    )

    assert assessment is not None
    assert assessment.standard.group == 3
    assert assessment.intensity == 5
    assert assessment.consistent
    assert "сплошное пятно" in lba_intensity_name(5, AppLanguage.RU)


def test_lba_assessment_preserves_and_reports_conflicting_observations() -> None:
    assessment = assess_lba_standard(
        group=2,
        type_id="СБ",
        color="Б — белый",
        intensity=4,
    )

    assert assessment is not None
    assert assessment.standard.code == "СБ"
    assert not assessment.consistent
    assert len(assessment.conflicts) == 2


def test_ambiguous_light_brown_colour_needs_group_or_type_context() -> None:
    assert {item.group for item in lba_groups_for_color("СК")} == {3, 4}
    assert (
        assess_lba_standard(
            group=None,
            type_id=None,
            color="СК",
            intensity=3,
        )
        is None
    )

@pytest.mark.parametrize(
    ("group", "code", "colours"),
    (
        (1, "ЛБ", ("БГ",)),
        (2, "МБ", ("Б", "ГЖ", "БЖ")),
        (3, "МСБ", ("Ж", "ОЖ", "СК")),
        (4, "СБ", ("ОК", "СК", "К")),
        (5, "САБ", ("ТК", "ЗК", "КК", "ЧК", "Ч")),
    ),
)
def test_operator_reference_chart_exact_type_palette(
    group: int, code: str, colours: tuple[str, ...],
) -> None:
    """The uploaded classification chart is the authoritative five-group palette."""
    record = LBA_STANDARD_GROUPS[group - 1]
    assert record.group == group
    assert record.code == code
    assert tuple(colour.code for colour in record.colors) == colours


@pytest.mark.parametrize("code", ("О", "ЖК", "СЖ"))
def test_additional_colour_alone_does_not_invent_florovskaya_group(code: str) -> None:
    assert lba_groups_for_color(code) == ()
    assert assess_lba_standard(
        group=None, type_id=None, color=code, intensity=2,
    ) is None


@pytest.mark.parametrize(
    ("score", "form"),
    (
        (1, "единичные точки"),
        (2, "прерывистое кольцо"),
        (3, "тонкое сплошное кольцо"),
        (4, "толстое кольцо"),
        (5, "сплошное пятно"),
    ),
)
def test_extracted_bitumen_quantity_scale_is_independent_of_type(
    score: int, form: str,
) -> None:
    assert lba_intensity_name(score, AppLanguage.RU) == form
    match = assess_lba_standard(
        group=4, type_id="СБ", color="К", intensity=score,
    )
    assert match is not None
    assert match.standard.group == 4
    assert match.intensity == score
    assert match.consistent


def test_group_two_matches_operator_chart_asphaltene_wording() -> None:
    group_two = LBA_STANDARD_GROUPS[1]
    assert "незначительно или нет" in group_two.composition_ru
    assert "little or no" in group_two.composition_en


def test_shared_light_brown_remains_ambiguous_without_group_or_type() -> None:
    assert {group.group for group in lba_groups_for_color("СК")} == {3, 4}
    assert assess_lba_standard(
        group=None, type_id=None, color="СК", intensity=5,
    ) is None


def test_known_color_conflicting_with_operator_group_is_reported() -> None:
    assessment = assess_lba_standard(
        group=1, type_id=None, color="ОЖ — оранжево-жёлтый", intensity=3,
    )
    assert assessment is not None
    assert assessment.standard.group == 3
    assert not assessment.consistent
    assert any("группа 1" in conflict for conflict in assessment.conflicts)

@pytest.mark.parametrize(
    ("language", "label"),
    (
        (AppLanguage.RU, "балл ЛБА по люминесцирующему пятну 2: прерывистое кольцо"),
        (AppLanguage.KK, "капиллярлық дақтың ЛБА балы 2: үзік сақина"),
        (AppLanguage.EN, "LBA capillary-spot score 2: fragmentary ring"),
    ),
)
def test_two_is_residual_ring_pattern_not_fluorescence_brightness(
    language: AppLanguage, label: str,
) -> None:
    assessment = assess_lba_standard(
        group=1, type_id="ЛБ", color="БГ", intensity=2,
    )
    assert assessment is not None
    description = describe_lba_assessment(assessment, language)
    assert label in description
    assert assessment.standard.group == 1


@pytest.mark.parametrize(
    ("language", "expected"),
    (
        (AppLanguage.RU, "ЛБА: люминесцирующее пятно"),
        (AppLanguage.KK, "ЛБА: люминесценттік дақ"),
        (AppLanguage.EN, "LBA fluorescence-spot"),
    ),
)
def test_tablet_translation_calls_the_legacy_intensity_field_a_residue_score(
    language: AppLanguage, expected: str,
) -> None:
    from geoworkbench.services.localization import Localizer

    assert expected in Localizer.create(language).text("tablet.lba_intensity")
