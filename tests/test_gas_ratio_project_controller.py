from __future__ import annotations

from pathlib import Path

import numpy as np

from geoworkbench.domain.models import Dataset, DatasetKind, DepthDomain
from geoworkbench.project.gas_ratio_controller import GasRatioProjectController
from geoworkbench.project.session import ProjectSession


ROOT = Path(__file__).resolve().parents[1]


def _session(dataset_id: str) -> ProjectSession:
    dataset = Dataset(
        dataset_id=dataset_id,
        name=f"Gas {dataset_id}",
        kind=DatasetKind.GTI,
        depth_domain=DepthDomain.MD,
        depth=np.array([1000.0, 1000.5, 1001.0, 1001.5]),
    )
    for mnemonic, value in {
        "C1": 80.0,
        "C2": 10.0,
        "C3": 5.0,
        "IC4": 1.0,
        "NC4": 2.0,
        "IC5": 1.0,
        "NC5": 1.0,
    }.items():
        dataset.upsert_curve(
            mnemonic,
            np.full(dataset.depth.shape, value, dtype=np.float64),
            unit="% abs",
            description=f"Source {mnemonic}",
            provenance="source:test",
        )
    session = ProjectSession()
    session.add_dataset(dataset)
    session.dirty = False
    return session


def test_controller_commits_conditioned_ratios_and_returns_dataset() -> None:
    session = _session("gas-source")
    dataset = session.current_dataset
    assert dataset is not None

    outcome = GasRatioProjectController(session).calculate_basic_ratios()

    assert outcome.dataset is dataset
    assert "TG_CALC" in outcome.created_mnemonics
    assert "PIXLER_C1_C2" in outcome.created_mnemonics
    total = dataset.curve_by_mnemonic("TG_CALC")
    assert total is not None
    assert total.metadata.provenance == "calculation:conditioned-gas-ratio:2.0"
    assert dataset.gas_conditioning_qc is not None
    assert session.dirty


def test_controller_uses_rebound_session() -> None:
    first = _session("first")
    second = _session("second")
    first_dataset = first.current_dataset
    second_dataset = second.current_dataset
    assert first_dataset is not None
    assert second_dataset is not None

    controller = GasRatioProjectController(first)
    controller.session = second
    outcome = controller.calculate_basic_ratios()

    assert outcome.dataset is second_dataset
    assert first_dataset.curve_by_mnemonic("TG_CALC") is None
    assert second_dataset.curve_by_mnemonic("TG_CALC") is not None
    assert not first.dirty
    assert second.dirty


def test_main_window_uses_gas_ratio_project_controller_boundary() -> None:
    source = (ROOT / "src/geoworkbench/ui/main_window.py").read_text(encoding="utf-8")
    start = source.index("def calculate_ratios")
    block = source[start : source.index("def _after_interpretation_calculation", start)]

    assert "GasRatioProjectController(self.session)" in source
    assert 'bindings.register(self.gas_ratio_project_controller, name="gas_ratio")' in source
    assert "self.gas_ratio_project_controller.calculate_basic_ratios()" in block
    assert "self.session.calculate_basic_gas_ratios()" not in block


def test_project_session_compatibility_shim_delegates_to_controller() -> None:
    session = _session("compat")

    created = session.calculate_basic_gas_ratios()

    assert "TG_CALC" in created
    assert session.current_dataset is not None
    assert session.current_dataset.curve_by_mnemonic("TG_CALC") is not None
