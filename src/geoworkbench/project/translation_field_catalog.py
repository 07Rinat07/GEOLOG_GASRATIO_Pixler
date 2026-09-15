from __future__ import annotations

from collections.abc import Mapping

from geoworkbench.domain.models import Well
from geoworkbench.domain.translation_readiness import TranslatableField


class WellTranslationFieldCatalog:
    """Project real multilingual well fields into stable WELL-04 field identities.

    The catalog is intentionally read-only.  It does not infer translation state
    from text presence and it does not mutate the persisted status registry.
    Optional fields become translation requirements only after at least one
    authored text variant exists.
    """

    @staticmethod
    def fields(well: Well) -> tuple[TranslatableField, ...]:
        result: list[TranslatableField] = []

        for interval in sorted(
            well.lithology,
            key=lambda item: (item.top_depth, item.bottom_depth, item.interval_id),
        ):
            if _has_authored_text(interval.description_i18n, interval.description):
                result.append(
                    _interval_field(
                        f"lithology/{interval.interval_id}/description",
                        "lithology.description",
                        interval.top_depth,
                        interval.bottom_depth,
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

        for interval in sorted(
            well.stratigraphy,
            key=lambda item: (item.top_depth, item.bottom_depth, item.interval_id),
        ):
            if _has_authored_text(interval.name_i18n, interval.name):
                result.append(
                    _interval_field(
                        f"stratigraphy/{interval.interval_id}/name",
                        "stratigraphy.name",
                        interval.top_depth,
                        interval.bottom_depth,
                    )
                )
            if _has_authored_text(interval.description_i18n, interval.description):
                result.append(
                    _interval_field(
                        f"stratigraphy/{interval.interval_id}/description",
                        "stratigraphy.description",
                        interval.top_depth,
                        interval.bottom_depth,
                    )
                )

        for interpretation in sorted(
            well.interpretations.values(),
            key=lambda item: (item.name.casefold(), item.interpretation_id),
        ):
            # Interpretation name is required by the model, therefore it is
            # always part of readiness.  Description remains optional.
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

            for interval in sorted(
                interpretation.intervals,
                key=lambda item: (item.top_depth, item.bottom_depth, item.interval_id),
            ):
                # Interval label is required by the model; comment is optional.
                result.append(
                    _interval_field(
                        (
                            f"interpretation/{interpretation.interpretation_id}/"
                            f"interval/{interval.interval_id}/label"
                        ),
                        "interpretation.interval_label",
                        interval.top_depth,
                        interval.bottom_depth,
                    )
                )
                if _has_authored_text(interval.comment_i18n, interval.comment):
                    result.append(
                        _interval_field(
                            (
                                f"interpretation/{interpretation.interpretation_id}/"
                                f"interval/{interval.interval_id}/comment"
                            ),
                            "interpretation.interval_comment",
                            interval.top_depth,
                            interval.bottom_depth,
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
