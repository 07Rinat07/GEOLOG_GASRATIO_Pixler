import copy

import numpy as np

import geoworkbench.services.acquisition as acquisition_module
from geoworkbench.domain.acquisition import (
    AcquisitionDataRowPayload,
    AcquisitionDatasetSchema,
    AcquisitionIndexSchema,
    AcquisitionRecord,
    AcquisitionRecordKind,
    AcquisitionSession,
)
from geoworkbench.domain.models import (
    Dataset,
    DatasetKind,
    DepthDomain,
    IndexRole,
    IndexType,
    Well,
)
from geoworkbench.services.acquisition import AcquisitionController, replay_acquisition_session


def _schema() -> AcquisitionDatasetSchema:
    return AcquisitionDatasetSchema(
        dataset_id="live-dataset",
        name="Live acquisition",
        kind=DatasetKind.GTI,
        depth_domain=DepthDomain.MD,
        indexes=(
            AcquisitionIndexSchema(
                index_id="depth-index",
                mnemonic="DEPT",
                index_type=IndexType.MD,
                role=IndexRole.DEPTH,
                unit="m",
            ),
        ),
        active_index_id="depth-index",
        curves=(),
    )


def _row(sequence: int, depth: float) -> AcquisitionRecord:
    return AcquisitionRecord(
        record_id=f"row-{sequence}",
        sequence=sequence,
        kind=AcquisitionRecordKind.DATA_ROW,
        payload=AcquisitionDataRowPayload(
            index_values=(("depth-index", depth),),
            curve_values=(),
        ),
        received_at=f"2026-09-02T10:{sequence:02d}:00+05:00",
        source="fixture:perf02",
    )


def _unrelated_dataset() -> Dataset:
    return Dataset(
        dataset_id="unrelated-dataset",
        name="Unrelated",
        kind=DatasetKind.USER,
        depth_domain=DepthDomain.MD,
        depth=np.arange(10_000, dtype=np.float64),
    )


def test_fresh_replay_does_not_deepcopy_well_or_unrelated_datasets(monkeypatch) -> None:
    source_well = Well("well-1", "Source")
    source_session = AcquisitionSession("session-1", source_well.well_id, _schema())
    source_controller = AcquisitionController(source_well, source_session)
    source_controller.append(_row(1, 100.0))

    target_well = Well("well-1", "Target")
    unrelated = _unrelated_dataset()
    target_well.datasets[unrelated.dataset_id] = unrelated

    def unexpected_deepcopy(value: object) -> object:
        raise AssertionError(f"fresh replay must not deepcopy {type(value).__name__}")

    monkeypatch.setattr(acquisition_module, "deepcopy", unexpected_deepcopy)
    result = replay_acquisition_session(source_session, target_well)

    assert result.records_replayed == 1
    assert target_well.datasets[unrelated.dataset_id] is unrelated
    assert target_well.datasets["live-dataset"].depth.tolist() == [100.0]
    assert target_well.acquisition_sessions["session-1"].records[0] is source_session.records[0]


def test_checkpoint_resume_copies_only_acquisition_dataset_and_reuses_immutable_journal(
    monkeypatch,
) -> None:
    source_well = Well("well-1", "Source")
    source_session = AcquisitionSession("session-1", source_well.well_id, _schema())
    source_controller = AcquisitionController(source_well, source_session)
    source_controller.append(_row(1, 100.0))
    checkpoint = source_controller.create_checkpoint(
        "checkpoint-1",
        created_at="2026-09-02T10:01:30+05:00",
    )
    source_controller.append(_row(2, 101.0))

    target_well = Well("well-1", "Target")
    target_session = AcquisitionSession("session-1", target_well.well_id, _schema())
    target_controller = AcquisitionController(target_well, target_session)
    target_controller.append(source_session.records[0])
    target_session.checkpoints.append(checkpoint)
    unrelated = _unrelated_dataset()
    target_well.datasets[unrelated.dataset_id] = unrelated

    copied_types: list[type[object]] = []

    def scoped_deepcopy(value: object) -> object:
        copied_types.append(type(value))
        assert isinstance(value, Dataset)
        assert value.dataset_id == "live-dataset"
        return copy.deepcopy(value)

    monkeypatch.setattr(acquisition_module, "deepcopy", scoped_deepcopy)
    result = replay_acquisition_session(
        source_session,
        target_well,
        checkpoint_id="checkpoint-1",
    )

    assert result.records_replayed == 1
    assert copied_types == [Dataset]
    assert target_well.datasets[unrelated.dataset_id] is unrelated
    assert target_controller.dataset.depth.tolist() == [100.0, 101.0]
    assert target_session.records == source_session.records
    assert all(
        target_record is source_record
        for target_record, source_record in zip(target_session.records, source_session.records)
    )
    assert target_session.checkpoints == source_session.checkpoints
