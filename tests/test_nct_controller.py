import numpy as np

from geoworkbench.domain.models import Dataset, DatasetKind, DepthDomain
from geoworkbench.project.nct_controller import NctCalculationController
from geoworkbench.project.session import ProjectSession


def make_controller() -> NctCalculationController:
    dataset = Dataset(
        "dataset", "Well", DatasetKind.GTI, DepthDomain.MD,
        np.array([1000.0, 1100.0, 1200.0, 1300.0]),
    )
    dataset.upsert_curve(
        "DEXPC", np.array([1.0, 1.1, 1.2, 0.9]),
        unit="dimensionless", provenance="calculation:dexp",
    )
    session = ProjectSession()
    session.add_dataset(dataset)
    session.dirty = False
    return NctCalculationController(session)


def test_nct_controller_creates_trend_and_deviation_curves() -> None:
    controller = make_controller()

    result = controller.calculate(1000.0, 1200.0)

    dataset = controller.session.current_dataset
    assert dataset is not None
    np.testing.assert_allclose(dataset.curve_by_mnemonic("NCT").values, result.trend)
    np.testing.assert_allclose(
        dataset.curve_by_mnemonic("DEXPC_NCT").values, result.deviation, atol=1e-12
    )
    assert result.deviation[-1] < 0.0
    assert dataset.curve_by_mnemonic("NCT").metadata.provenance.startswith(
        "calculation:nct.linear:v1:"
    )
    assert controller.session.dirty is True
