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
