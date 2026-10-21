"""Presence of saved LBA observations, independent of their interpretation."""

from __future__ import annotations


LBA_OBSERVATION_FIELDS = (
    "lba_group", "lba_type_id", "lba_intensity", "lba_color",
    "lba_distribution", "lba_cut", "lba_cut_speed", "lba_cut_color",
    "lba_residue_type", "lba_residue_color", "lba_odour", "lba_stain",
    "lba_description",
)


def has_recorded_lba(sample: object) -> bool:
    """Any recorded field is evidence of an observation, not a fluid class.

    Older render models may omit optional detail fields; that is missing data.
    Empty text stays missing, while a recorded numeric zero remains present.
    """
    return any(
        value is not None and (not isinstance(value, str) or bool(value.strip()))
        for name in LBA_OBSERVATION_FIELDS
        for value in (getattr(sample, name, None),)
    )
