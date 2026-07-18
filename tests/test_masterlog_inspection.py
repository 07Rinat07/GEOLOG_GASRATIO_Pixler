import numpy as np
from PySide6.QtCore import QPointF, QRectF

from geoworkbench.domain.models import (
    CurveData,
    CurveMetadata,
    CuttingsSample,
    Dataset,
    DatasetKind,
    DepthDomain,
    LithologyInterval,
    MasterlogColumnTemplate,
    MasterlogTemplate,
    ProjectLithotype,
    StratigraphyInterval,
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


def test_click_on_calcimetry_and_lba_returns_sample_interval() -> None:
    session = _session()
    assert session.current_well is not None
    session.current_well.cuttings.append(
        CuttingsSample(
            "sample",
            400.0,
            600.0,
            calcite_percent=60.0,
            dolomite_percent=25.0,
            lba_type_id="Oil show",
            lba_intensity=4,
            lba_color="yellow",
            lba_cut="Streaming",
            analysis_interpretation="Manual show interpretation",
        )
    )
    template = MasterlogTemplate(
        "form",
        "Form",
        header_height_mm=45.0,
        columns=[
            MasterlogColumnTemplate("calc", "Calcimetry", "calcimetry", 50.0),
            MasterlogColumnTemplate("lba", "LBA", "lba", 50.0),
        ],
    )

    calc = inspect_masterlog_point(QPointF(47.0, 128.5), QRectF(0, 0, 100, 257), template, session)
    lba = inspect_masterlog_point(
        QPointF(53.0, 128.5),
        QRectF(0, 0, 100, 257),
        template,
        session,
        language=AppLanguage.EN,
    )

    assert calc is not None and calc.interval == (400.0, 600.0)
    assert calc.description == (
        "Кальцит CaCO₃: 60%; Доломит CaMg(CO₃)₂: 25%; Нерастворимый остаток: 15%; "
        "Интерпретация геолога: Manual show interpretation"
    )
    assert lba is not None and lba.interval == (400.0, 600.0)
    assert lba.description == (
        "Oil show; Intensity: 4; yellow; Streaming; "
        "Geologist interpretation: Manual show interpretation"
    )


def test_click_on_stratigraphy_reports_nested_units_and_narrowest_interval() -> None:
    session = _session()
    assert session.current_well is not None
    session.current_well.stratigraphy.extend(
        [
            StratigraphyInterval("period", 0.0, 1000.0, "K", "Cretaceous", "System / Period"),
            StratigraphyInterval(
                "stage", 400.0, 600.0, "K1a", "Albian", "Stage / Age", description="Target"
            ),
        ]
    )
    template = MasterlogTemplate(
        "form",
        "Form",
        header_height_mm=45.0,
        columns=[MasterlogColumnTemplate("strat", "Stratigraphy", "stratigraphy", 100.0)],
    )

    result = inspect_masterlog_point(
        QPointF(50.0, 128.5), QRectF(0, 0, 100, 257), template, session
    )

    assert result is not None
    assert result.interval == (400.0, 600.0)
    assert "Stage / Age / K1a / Albian — Target" in result.description
    assert "System / Period / K / Cretaceous" in result.description
