import numpy as np
from PySide6.QtCore import QPointF, QRectF

from geoworkbench.domain.models import (
    CurveData,
    CurveMetadata,
    Dataset,
    DatasetKind,
    DepthDomain,
    LithologyInterval,
    MasterlogColumnTemplate,
    MasterlogTemplate,
    ProjectLithotype,
)
from geoworkbench.printing.masterlog_inspection import inspect_masterlog_point
from geoworkbench.project.session import ProjectSession
from geoworkbench.services.localization import AppLanguage


def _session() -> ProjectSession:
    session = ProjectSession()
    dataset = Dataset(
        "data",
        "Well log",
        DatasetKind.GTI,
        DepthDomain.MD,
        np.array([0.0, 500.0, 1000.0]),
    )
    dataset.curves["tg"] = CurveData(
        CurveMetadata("tg", "TG", "TG", "%", "Total Gas", "data"),
        np.array([0.1, 1.0, 2.0]),
    )
    well = session.add_dataset(dataset, "Well A")
    session.project.lithotypes["sand"] = ProjectLithotype(
        "sand", "S", "Песчаник", "Sandstone", "sedimentary", "#ffee00", "solid", "Құмтас"
    )
    well.lithology.append(LithologyInterval("layer", 400.0, 600.0, "sand", "Fine grained"))
    return session


def test_click_on_curve_returns_nearest_value_and_depth() -> None:
    session = _session()
    template = MasterlogTemplate(
        "form",
        "Form",
        header_height_mm=45.0,
        columns=[MasterlogColumnTemplate("gas", "Gas", "curves", 100.0, ["TG"], x_min=0, x_max=2)],
    )

    result = inspect_masterlog_point(
        QPointF(50.0, 128.5), QRectF(0, 0, 100, 257), template, session
    )

    assert result is not None
    assert result.mnemonic == "TG"
    assert result.value == 1.0
    assert result.depth == 500.0
    assert result.display_text(AppLanguage.RU) == "Gas\nTG: 1 %\nГлубина: 500 м\nTotal Gas"


def test_click_on_lithology_returns_interval_and_description() -> None:
    session = _session()
    template = MasterlogTemplate(
        "form",
        "Form",
        header_height_mm=45.0,
        columns=[MasterlogColumnTemplate("lith", "Lithology", "lithology", 100.0)],
    )

    result = inspect_masterlog_point(
        QPointF(50.0, 128.5),
        QRectF(0, 0, 100, 257),
        template,
        session,
        language=AppLanguage.KK,
    )

    assert result is not None
    assert result.interval == (400.0, 600.0)
    assert result.description == "Құмтас — Fine grained"
