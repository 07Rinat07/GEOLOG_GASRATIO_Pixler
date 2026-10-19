import pytest

from geoworkbench.services.lba_standard import (
    LBA_STANDARD_GROUPS,
    assess_lba_standard,
    lba_groups_for_color,
    lba_intensity_name,
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

@pytest.mark.parametrize("code", ("Ж", "О", "ОЖ", "ЖК"))
def test_published_florovskaya_group_three_colors_are_resolvable(code: str) -> None:
    """Published shorthand in the classic III (oily-resinous) range."""
    assert [group.group for group in lba_groups_for_color(code)] == [3]
    assessment = assess_lba_standard(
        group=None, type_id=None, color=code, intensity=2,
    )
    assert assessment is not None
    assert assessment.standard.code == "МСБ"
    assert assessment.intensity == 2
    assert assessment.consistent


def test_group_two_does_not_claim_all_asphaltenes_are_absent() -> None:
    group_two = LBA_STANDARD_GROUPS[1]
    assert "мало или нет" in group_two.composition_ru
    assert "little or no" in group_two.composition_en


def test_light_brown_ambiguity_survives_extended_group_three_palette() -> None:
    assert {group.group for group in lba_groups_for_color("СК")} == {3, 4}
    assert assess_lba_standard(
        group=None, type_id=None, color="СК", intensity=5,
    ) is None


def test_published_group_three_with_foreign_group_one_is_flagged() -> None:
    assessment = assess_lba_standard(
        group=1, type_id=None, color="О — оранжевый", intensity=3,
    )
    assert assessment is not None
    assert assessment.standard.group == 3
    assert not assessment.consistent
    assert any("группа 1" in conflict for conflict in assessment.conflicts)
