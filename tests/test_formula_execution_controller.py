import numpy as np
import pytest

from geoworkbench.calculations.controller import FormulaExecutionController
from geoworkbench.calculations.pixler import build_all_sourced_formula_registry
from geoworkbench.domain.models import Dataset, DatasetKind, DepthDomain
from geoworkbench.project.session import ProjectSession


def make_session() -> ProjectSession:
    dataset = Dataset("dataset", "Drilling", DatasetKind.GTI, DepthDomain.MD, np.array([1.0, 2.0]))
    for mnemonic, unit, values in (
        ("ROP", "ft/h", [60.0, 120.0]),
        ("RPM", "rpm", [100.0, 100.0]),
        ("WOB", "lbf", [50_000.0, 50_000.0]),
        ("BS", "in", [10.0, 10.0]),
    ):
        dataset.upsert_curve(mnemonic, np.array(values), unit=unit, provenance="source")
    session = ProjectSession()
    session.add_dataset(dataset)
    session.dirty = False
    return session


def test_controller_executes_profile_with_explicit_mapping() -> None:
    session = make_session()
    controller = FormulaExecutionController(session, build_all_sourced_formula_registry())

    result = controller.execute(
        "dexp.jorden_shirley",
        {"ROP_FPH": "ROP", "RPM": "RPM", "WOB_LBF": "WOB", "BIT_IN": "BS"},
    )

    assert result.output_mnemonic == "DEXP"
    assert result.curve.metadata.provenance == "calculation:dexp.jorden_shirley:1.0.0"
    assert result.curve.metadata.unit == "dimensionless"
    assert session.current_dataset is not None
    assert session.current_dataset.curve_by_mnemonic("DEXP") is result.curve
    assert session.dirty is True


def test_controller_rejects_wrong_units_and_source_overwrite() -> None:
    session = make_session()
    assert session.current_dataset is not None
    controller = FormulaExecutionController(session, build_all_sourced_formula_registry())

    with pytest.raises(ValueError, match="перезаписать исходную"):
        controller.execute(
            "dexp.jorden_shirley",
            {"ROP_FPH": "ROP", "RPM": "RPM", "WOB_LBF": "WOB", "BIT_IN": "BS"},
            output_mnemonic="ROP",
        )

    wob = session.current_dataset.curve_by_mnemonic("WOB")
    assert wob is not None
    object.__setattr__(wob.metadata, "unit", "kg")
    with pytest.raises(ValueError, match="ожидалась lbf"):
        controller.execute(
            "dexp.jorden_shirley",
            {"ROP_FPH": "ROP", "RPM": "RPM", "WOB_LBF": "WOB", "BIT_IN": "BS"},
        )


def test_controller_requires_complete_mapping() -> None:
    controller = FormulaExecutionController(make_session(), build_all_sourced_formula_registry())
    with pytest.raises(KeyError, match="BIT_IN"):
        controller.execute(
            "dexp.jorden_shirley",
            {"ROP_FPH": "ROP", "RPM": "RPM", "WOB_LBF": "WOB"},
        )


def test_controller_creates_normalized_gas_curve() -> None:
    session = make_session()
    assert session.current_dataset is not None
    for mnemonic, unit, values in (
        ("C1", "%", [10.0, 20.0]),
        ("FLOW", "gpm", [500.0, 500.0]),
    ):
        session.current_dataset.upsert_curve(
            mnemonic, np.array(values), unit=unit, provenance="source"
        )
    controller = FormulaExecutionController(session, build_all_sourced_formula_registry())

    result = controller.execute(
        "gas.normalized_c1_us20140379265",
        {"C1": "C1", "FLOW_GPM": "FLOW", "ROP_FPH": "ROP", "BIT_IN": "BS"},
    )

    assert result.output_mnemonic == "C1_NORM"
    assert result.curve.metadata.provenance.startswith(
        "calculation:gas.normalized_c1_us20140379265:"
    )
    np.testing.assert_allclose(result.curve.values, [29.0 / 3.0, 29.0 / 3.0])
