import numpy as np
import pytest

from geoworkbench.domain.models import CurveData, CurveMetadata, Dataset, DatasetKind, DepthDomain
from geoworkbench.project.dataset_merge_controller import DatasetMergeController
from geoworkbench.project.session import ProjectSession
from geoworkbench.tablet.models import TabletLayout


def make_controller() -> tuple[DatasetMergeController, Dataset, Dataset]:
    session = ProjectSession()
    source = Dataset("source", "Source", DatasetKind.GIS, DepthDomain.MD, np.array([100.0, 101.0]))
    source.curves["gr"] = CurveData(
        CurveMetadata("gr", "GR", "GR", "API", None, source.dataset_id),
        np.array([10.0, 11.0]),
    )
    target = Dataset("target", "Target", DatasetKind.GTI, DepthDomain.MD, np.array([101.0, 102.0]))
    target.curves["rop"] = CurveData(
        CurveMetadata("rop", "ROP", "ROP", "m/h", None, target.dataset_id),
        np.array([20.0, 21.0]),
    )
    session.add_dataset(source)
    session.add_dataset(target)
    session.dirty = False
    return DatasetMergeController(session), source, target


def test_merge_controller_creates_copy_and_supports_undo_redo() -> None:
    controller, source, target = make_controller()

    result = controller.create(source.dataset_id, controller.analyze(source.dataset_id))

    well = controller.session.current_well
    assert well is not None
    assert controller.session.current_dataset is result
    assert set(well.datasets) == {"source", "target", result.dataset_id}
    layout = TabletLayout()
    controller.session.tablet_layouts[result.dataset_id] = layout
    controller.undo()
    assert controller.session.current_dataset is target
    assert set(well.datasets) == {"source", "target"}
    assert result.dataset_id not in controller.session.tablet_layouts
    assert controller.redo() is result
    assert controller.session.current_dataset is result
    assert controller.session.tablet_layouts[result.dataset_id] is layout


def test_merge_controller_blocks_undo_after_result_edit() -> None:
    controller, source, _ = make_controller()
    result = controller.create(source.dataset_id, controller.analyze(source.dataset_id))
    result.curve_by_mnemonic("GR").values[0] = 99.0

    with pytest.raises(RuntimeError, match="последующие правки"):
        controller.undo()


def test_merge_copy_preserves_target_lossless_artifact_for_export() -> None:
    from geoworkbench.data.las_import_report import LasImportReport, LasSourceSnapshot
    from geoworkbench.data.lossless_las import parse_lossless_las
    from geoworkbench.services.depth_axis import analyze_depth_axis
    from pathlib import Path

    controller, source, target = make_controller()
    raw = b"~V\nVERS.2.0\n~Other\nCUSTOM CONTENT\n~A\n"
    document = parse_lossless_las(raw)
    report = LasImportReport(
        LasSourceSnapshot(
            Path("target.las"),
            len(raw),
            document.sha256,
            document.encoding,
            document.newline_style.value,
            tuple(section.name for section in document.sections),
            "2.0",
            "NO",
            -999.25,
        ),
        analyze_depth_axis(target.depth),
        (),
    )
    controller.session.source_documents[target.dataset_id] = document
    controller.session.import_reports[target.dataset_id] = report

    result = controller.create(source.dataset_id, controller.analyze(source.dataset_id))

    assert controller.session.source_documents[result.dataset_id] is document
    assert controller.session.import_reports[result.dataset_id] is report
    controller.undo()
    assert result.dataset_id not in controller.session.source_documents
    assert result.dataset_id not in controller.session.import_reports
    controller.redo()
    assert controller.session.source_documents[result.dataset_id] is document
    assert controller.session.import_reports[result.dataset_id] is report


def test_merge_keeps_well_annotations_across_create_undo_and_redo() -> None:
    from geoworkbench.project.annotation_controller import AnnotationController
    from geoworkbench.project.annotation_schema import AnnotationAnchor, AnnotationKind

    controller, source, _ = make_controller()
    annotation_controller = AnnotationController(controller.session)
    annotation = annotation_controller.add_annotation(
        kind=AnnotationKind.COMMENT,
        anchor=AnnotationAnchor.DEPTH,
        text="Рейс долота №12",
        depth=101.5,
        track_id="drilling",
        print_enabled=True,
    )
    well = controller.session.current_well
    assert well is not None

    result = controller.create(source.dataset_id, controller.analyze(source.dataset_id))
    assert any(item.object_id == annotation.annotation_id for item in well.canvas_objects)

    controller.undo()
    assert any(item.object_id == annotation.annotation_id for item in well.canvas_objects)

    assert controller.redo() is result
    assert any(item.object_id == annotation.annotation_id for item in well.canvas_objects)
