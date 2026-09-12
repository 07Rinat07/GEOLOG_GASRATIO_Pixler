"""Project-session boundary for profile-bound geology updates.

The low-level WELL-02 geology service accepts a ``RockCodeDictionary`` so it can
remain independently testable. Production project workflows must not choose an
arbitrary/current supplier dictionary, though: project v29 persists an immutable
``source_sha256 -> profile_sha256`` binding. This module resolves that exact
revision from the active ``ProjectSession`` before preview and revalidates the
binding again before prepare/commit.
"""
from __future__ import annotations

from typing import TYPE_CHECKING

from geoworkbench.services.daily_las_growth import DailyLasGrowthError
from geoworkbench.services.persisted_rock_code_profiles import (
    PersistedRockCodeProfileResolver,
)
from geoworkbench.services.well_geology_update import (
    PreparedGeologyUpdate,
    WellGeologyUpdatePlan,
    analyze_well_geology_update,
    prepare_well_geology_update,
)

if TYPE_CHECKING:
    from geoworkbench.domain.models import Dataset
    from geoworkbench.project.session import ProjectSession


def analyze_persisted_well_geology_update(
    session: ProjectSession,
    target: Dataset,
    source: Dataset,
    *,
    source_name: str,
    source_sha256: str,
) -> WellGeologyUpdatePlan:
    """Analyze geology using only the exact profile persisted for ``source_sha256``."""

    resolved = PersistedRockCodeProfileResolver.from_session(session).require(source_sha256)
    return analyze_well_geology_update(
        session,
        target,
        source,
        resolved.dictionary,
        source_name=source_name,
        source_sha256=source_sha256,
    )


def prepare_persisted_well_geology_update(
    session: ProjectSession,
    target: Dataset,
    source: Dataset,
    plan: WellGeologyUpdatePlan,
    *,
    source_name: str,
    source_sha256: str,
    append_rows: bool,
) -> PreparedGeologyUpdate | None:
    """Revalidate the persisted binding, then prepare the already-reviewed update.

    Re-resolving here prevents a preview made for one immutable profile revision
    from being committed after the source binding has been replaced or removed.
    ``prepare_well_geology_update`` still performs its complete dataset/well/profile
    stale-plan comparison afterwards.
    """

    resolved = PersistedRockCodeProfileResolver.from_session(session).require(source_sha256)
    if resolved.profile.profile_sha256 != plan.profile_sha256:
        raise DailyLasGrowthError(
            "Привязка источника к профилю пород изменилась; повторите анализ"
        )
    return prepare_well_geology_update(
        session,
        target,
        source,
        plan,
        source_name=source_name,
        source_sha256=source_sha256,
        append_rows=append_rows,
    )
