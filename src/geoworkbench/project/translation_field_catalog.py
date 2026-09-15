from __future__ import annotations

from collections.abc import Mapping

from geoworkbench.domain.models import Well
from geoworkbench.domain.translation_readiness import TranslatableField


class WellTranslationFieldCatalog:
    """Project real multilingual well fields into stable WELL-04 field identities.

    The catalog is intentionally read-only. It does not infer translation state
    from text presence and it does not mutate the persisted status registry.
    Optional fields become translation requirements only after at least one
    authored text variant exists.
    """

    @staticmethod
    def fields(well: Well) -> tuple[TranslatableField, ...]:
        result: list[TranslatableField] = []

        for lithology_interval in sorted(
            well.lithology,
            key=lambda item: (item.top_depth, item.bottom_depth, item.interval_id),
        ):
            if _has_authored_text(
                lithology_interval.description_i18n,
                lithology_interval.description,
            ):
                result.append(
                    _interval_field(
                        f"lithology/{lithology_interval.interval_id}/description",
                        "lithology.description",
                        lithology_interval.top_depth,
                        lithology_interval.bottom_depth,
                    )
                )

        for sample in sorted(
            well.cuttings,
            key=lambda item: (item.top_depth, item.bottom_depth, item.sample_id),
        ):
            for suffix, label, localized, legacy in (
                (
                    "description",
                    "cuttings.description",
                    sample.description_i18n,
                    sample.description,
                ),
                (
                    "lba_description",
                    "cuttings.lba_description",
                    sample.lba_description_i18n,
                    sample.lba_description,
                ),
                (
                    "analysis_interpretation",
                    "cuttings.analysis_interpretation",
                    sample.analysis_interpretation_i18n,
                    sample.analysis_interpretation,
                ),
            ):
                if _has_authored_text(localized, legacy):
                    result.append(
                        _interval_field(
                            f"cuttings/{sample.sample_id}/{suffix}",
                            label,
                            sample.top_depth,
                            sample.bottom_depth,
                        )
                    )

        for stratigraphy_interval in sorted(
            well.stratigraphy,
            key=lambda item: (item.top_depth, item.bottom_depth, item.interval_id),
        ):
            if _has_authored_text(
                stratigraphy_interval.name_i18n,
                stratigraphy_interval.name,
            ):
                result.append(
                    _interval_field(
                        f"stratigraphy/{stratigraphy_interval.interval_id}/name",
                        "stratigraphy.name",
                        stratigraphy_interval.top_depth,
                        stratigraphy_interval.bottom_depth,
                    )
                )
            if _has_authored_text(
                stratigraphy_interval.description_i18n,
                stratigraphy_interval.description,
            ):
                result.append(
                    _interval_field(
                        f"stratigraphy/{stratigraphy_interval.interval_id}/description",
                        "stratigraphy.description",
                        stratigraphy_interval.top_depth,
                        stratigraphy_interval.bottom_depth,
                    )
                )

        for interpretation in sorted(
            well.interpretations.values(),
            key=lambda item: (item.name.casefold(), item.interpretation_id),
        ):
            # Interpretation name is required by the model, therefore it is
            # always part of readiness. Description remains optional.
            result.append(
                TranslatableField(
                    f"interpretation/{interpretation.interpretation_id}/name",
                    "interpretation.name",
                )
            )
            if _has_authored_text(
                interpretation.description_i18n,
                interpretation.description,
            ):
                result.append(
                    TranslatableField(
                        f"interpretation/{interpretation.interpretation_id}/description",
                        "interpretation.description",
                    )
                )

            for interpretation_interval in sorted(
                interpretation.intervals,
                key=lambda item: (item.top_depth, item.bottom_depth, item.interval_id),
            ):
                # Interval label is required by the model; comment is optional.
                result.append(
                    _interval_field(
                        (
                            f"interpretation/{interpretation.interpretation_id}/"
                            f"interval/{interpretation_interval.interval_id}/label"
                        ),
                        "interpretation.interval_label",
                        interpretation_interval.top_depth,
                        interpretation_interval.bottom_depth,
                    )
                )
                if _has_authored_text(
                    interpretation_interval.comment_i18n,
                    interpretation_interval.comment,
                ):
                    result.append(
                        _interval_field(
                            (
                                f"interpretation/{interpretation.interpretation_id}/"
                                f"interval/{interpretation_interval.interval_id}/comment"
                            ),
                            "interpretation.interval_comment",
                            interpretation_interval.top_depth,
                            interpretation_interval.bottom_depth,
                        )
                    )

        return tuple(result)


def _interval_field(
    field_id: str,
    label: str,
    top_depth: float,
    bottom_depth: float,
) -> TranslatableField:
    return TranslatableField(field_id, label, float(top_depth), float(bottom_depth))


def _has_authored_text(localized: Mapping[str, str], legacy: str | None) -> bool:
    if legacy is not None and legacy.strip():
        return True
    return any(isinstance(value, str) and bool(value.strip()) for value in localized.values())
