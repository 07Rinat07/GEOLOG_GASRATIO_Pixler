import numpy as np

from geoworkbench.domain.models import Dataset, DatasetKind, DepthDomain
from geoworkbench.project.depth_axis_controller import DepthAxisController
from geoworkbench.project.session import ProjectSession
from geoworkbench.services.depth_axis import DepthDirection


def test_controller_adds_ascending_copy_without_replacing_source() -> None:
    session = ProjectSession()
    source = Dataset("source", "GIS", DatasetKind.GIS, DepthDomain.MD, np.array([2.0, 1.0, 0.0]))
    well = session.add_dataset(source)
    session.dirty = False
    controller = DepthAxisController(session)

    assert controller.analyze_current().direction is DepthDirection.DESCENDING
    result = controller.create_ascending_copy()

    assert set(well.datasets) == {"source", result.dataset_id}
    assert session.current_dataset is result
    assert session.dirty is True
    np.testing.assert_allclose(source.depth, [2.0, 1.0, 0.0])

    assert controller.can_undo_ascending_copy
    controller.undo_ascending_copy()
    assert session.current_dataset is source
    assert set(well.datasets) == {"source"}
    assert controller.can_redo_ascending_copy

    assert controller.redo_ascending_copy() is result
    assert session.current_dataset is result
    assert set(well.datasets) == {"source", result.dataset_id}


def test_controller_resample_copy_supports_undo_and_redo() -> None:
    session = ProjectSession()
    source = Dataset("source", "LAS", DatasetKind.GTI, DepthDomain.MD, np.array([0.0, 1.0, 2.0]))
    well = session.add_dataset(source)
    controller = DepthAxisController(session)

    plan = controller.analyze_resample(0.0, 2.0, 0.5)
    result = controller.create_resampled_copy(plan)
    assert session.current_dataset is result
    assert set(well.datasets) == {"source", result.dataset_id}

    controller.undo_resample()
    assert session.current_dataset is source
    assert set(well.datasets) == {"source"}

    assert controller.redo_resample() is result
    assert session.current_dataset is result
    assert set(well.datasets) == {"source", result.dataset_id}


def test_ascending_copy_preserves_lossless_source_artifact_across_undo_redo() -> None:
    from pathlib import Path

    from geoworkbench.data.las_import_report import LasImportReport, LasSourceSnapshot
    from geoworkbench.data.lossless_las import parse_lossless_las
    from geoworkbench.services.depth_axis import analyze_depth_axis

    session = ProjectSession()
    source = Dataset("source", "LAS", DatasetKind.GTI, DepthDomain.MD, np.array([2.0, 1.0]))
    session.add_dataset(source)
    raw = b"~V\nVERS.2.0\n~Other\nPRESERVE ME\n~A\n"
    document = parse_lossless_las(raw)
    report = LasImportReport(
        LasSourceSnapshot(
            Path("descending.las"),
            len(raw),
            document.sha256,
            document.encoding,
            document.newline_style.value,
            tuple(section.name for section in document.sections),
            "2.0",
            "NO",
            -999.25,
        ),
        analyze_depth_axis(source.depth),
        (),
    )
    session.source_documents[source.dataset_id] = document
    session.import_reports[source.dataset_id] = report
    controller = DepthAxisController(session)

    result = controller.create_ascending_copy()
    assert session.source_documents[result.dataset_id] is document
    assert session.import_reports[result.dataset_id] is report
    controller.undo_ascending_copy()
    assert result.dataset_id not in session.source_documents
    assert result.dataset_id not in session.import_reports
    controller.redo_ascending_copy()
    assert session.source_documents[result.dataset_id] is document
    assert session.import_reports[result.dataset_id] is report
