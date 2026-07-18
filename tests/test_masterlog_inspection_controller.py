import numpy as np

from geoworkbench.domain.models import Dataset, DatasetKind, DepthDomain, MasterlogTemplate
from geoworkbench.printing.masterlog_inspection import MasterlogInspection
from geoworkbench.project.masterlog_inspection_controller import (
    MasterlogInspectionController,
)
from geoworkbench.project.session import ProjectSession
from geoworkbench.services.localization import AppLanguage


def test_pin_inspection_creates_printable_template_scoped_callout() -> None:
    session = ProjectSession()
    session.add_dataset(
        Dataset("data", "Log", DatasetKind.GTI, DepthDomain.MD, np.array([0.0, 1000.0])),
        "Well",
    )
    template = MasterlogTemplate("form", "Masterlog")
    inspection = MasterlogInspection("gas", "Gas", 500.0, "TG", 1.0, "%", "Total Gas")

    item = MasterlogInspectionController(session).pin(template, inspection, AppLanguage.RU)

    assert item.object_type == "masterlog_inspection"
    assert item.track_id == "gas"
    assert item.top_depth == 500.0
    assert item.properties["template_id"] == "form"
    assert "TG: 1 %" in str(item.properties["text"])
    assert session.dirty is True


def test_pin_interval_preserves_top_and_bottom() -> None:
    session = ProjectSession()
    session.add_dataset(
        Dataset("data", "Log", DatasetKind.GTI, DepthDomain.MD, np.array([0.0, 1000.0])),
        "Well",
    )
    inspection = MasterlogInspection(
        "lith", "Lithology", 505.0, description="Sandstone", interval=(500.0, 510.0)
    )

    item = MasterlogInspectionController(session).pin(
        MasterlogTemplate("form", "Masterlog"), inspection, AppLanguage.EN
    )

    assert item.anchor_type == "interval"
    assert (item.top_depth, item.bottom_depth) == (500.0, 510.0)
