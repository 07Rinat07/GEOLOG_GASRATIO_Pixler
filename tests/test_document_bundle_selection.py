from __future__ import annotations

import numpy as np
import pytest

from geoworkbench.domain.document_bundle import DocumentBundleScopeKind
from geoworkbench.domain.models import (
    Dataset,
    DatasetKind,
    DepthDomain,
    MasterlogTemplate,
    Project,
    Well,
)
from geoworkbench.project.document_bundle_selection import (
    DocumentBundleSelectionController,
    DocumentBundleSelectionError,
)
from geoworkbench.project.session import ProjectSession


def _controller() -> DocumentBundleSelectionController:
    dataset = Dataset(
        "dataset-1",
        "Dataset",
        DatasetKind.GTI,
        DepthDomain.MD,
        np.array([1000.0, 1100.0]),
    )
    well = Well(
        "well-1",
        "Well",
        datasets={dataset.dataset_id: dataset},
    )
    templates = (
        MasterlogTemplate("a4", "A4 Gas Log", page_format="A4"),
        MasterlogTemplate("roll", "Roll / Field", page_format="roll"),
    )
    project = Project(
        "project-1",
        "Project",
        wells={well.well_id: well},
        masterlog_templates={item.template_id: item for item in templates},
    )
    return DocumentBundleSelectionController(
        ProjectSession(
            project=project,
            current_well_id=well.well_id,
            current_dataset_id=dataset.dataset_id,
            dirty=False,
        )
    )


def test_masterlog_options_are_stable_safe_and_orientation_aware() -> None:
    controller = _controller()

    options = controller.masterlog_options(
        well_id="well-1",
        dataset_id="dataset-1",
    )

    assert [item.source_id for item in options] == ["a4", "roll"]
    assert options[0].supported_orientations == ("portrait", "landscape")
    assert options[1].supported_orientations == ("portrait",)
    assert options[0].target_name.endswith(".pdf")
    assert "/" not in options[1].target_name
    assert "\\" not in options[1].target_name
    assert options[0].output_id == "masterlog:a4:dataset-1"


def test_build_request_binds_selected_outputs_languages_and_interval() -> None:
    controller = _controller()
    option = controller.masterlog_options(
        well_id="well-1",
        dataset_id="dataset-1",
    )[0]

    request = controller.build_request(
        well_id="well-1",
        selected_outputs=(option,),
        languages=("ru", "kk"),
        orientations=("portrait", "landscape"),
        scope_kind=DocumentBundleScopeKind.INTERVAL,
        top_depth=1020.0,
        bottom_depth=1080.0,
        allow_drafts=True,
    )

    assert request.well_id == "well-1"
    assert request.output_ids == (option.output_id,)
    assert request.output_specs == (option.to_spec(),)
    assert request.languages == ("ru", "kk")
    assert request.orientations == ("portrait", "landscape")
    assert request.scope.top_depth == 1020.0
    assert request.scope.bottom_depth == 1080.0
    assert request.allow_drafts is True


def test_build_request_rejects_landscape_for_selected_roll_form() -> None:
    controller = _controller()
    roll = controller.masterlog_options(
        well_id="well-1",
        dataset_id="dataset-1",
    )[1]

    with pytest.raises(DocumentBundleSelectionError, match="does not support"):
        controller.build_request(
            well_id="well-1",
            selected_outputs=(roll,),
            languages=("ru",),
            orientations=("landscape",),
            scope_kind=DocumentBundleScopeKind.WHOLE_WELL,
        )


def test_options_require_dataset_from_selected_well() -> None:
    controller = _controller()

    with pytest.raises(DocumentBundleSelectionError, match="not part"):
        controller.masterlog_options(
            well_id="well-1",
            dataset_id="missing",
        )


def test_build_request_rejects_empty_output_selection() -> None:
    controller = _controller()

    with pytest.raises(DocumentBundleSelectionError, match="at least one"):
        controller.build_request(
            well_id="well-1",
            selected_outputs=(),
            languages=("ru",),
            orientations=("portrait",),
            scope_kind=DocumentBundleScopeKind.WHOLE_WELL,
        )
