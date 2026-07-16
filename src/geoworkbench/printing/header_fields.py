from __future__ import annotations

from geoworkbench.project.session import ProjectSession


SUPPORTED_HEADER_FIELDS = (
    "project.name",
    "well.name",
    "dataset.name",
)


def resolve_header_field(session: ProjectSession, field_name: str) -> str | None:
    if field_name == "project.name":
        return session.project.name
    if field_name == "well.name":
        return session.current_well.name if session.current_well is not None else None
    if field_name == "dataset.name":
        return session.current_dataset.name if session.current_dataset is not None else None
    return None
