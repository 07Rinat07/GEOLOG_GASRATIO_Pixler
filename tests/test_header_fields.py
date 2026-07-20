import numpy as np

from geoworkbench.domain.models import Dataset, DatasetKind, DepthDomain, Project, Well
from geoworkbench.printing.header_fields import resolve_header_field
from geoworkbench.project.session import ProjectSession


def make_session() -> ProjectSession:
    dataset = Dataset("dataset", "Logging", DatasetKind.GTI, DepthDomain.MD, np.array([1.0]))
    well = Well("well", "Well A", datasets={dataset.dataset_id: dataset})
    return ProjectSession(
        project=Project("project", "Project A", wells={well.well_id: well}),
        current_well_id=well.well_id,
        current_dataset_id=dataset.dataset_id,
    )


def test_header_field_resolver_uses_explicit_whitelist() -> None:
    session = make_session()

    assert resolve_header_field(session, "project.name") == "Project A"
    assert resolve_header_field(session, "well.name") == "Well A"
    assert resolve_header_field(session, "dataset.name") == "Logging"
    assert resolve_header_field(session, "project.__dict__") is None
