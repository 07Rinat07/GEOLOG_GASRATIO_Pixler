import numpy as np

from geoworkbench.domain.models import (
    Dataset,
    DatasetIndex,
    DatasetKind,
    DepthDomain,
    IndexRole,
    IndexType,
    TimeDepthAggregationPolicy,
)
from geoworkbench.project.session import ProjectSession
from geoworkbench.project.time_depth_mapping_controller import TimeDepthMappingController
from geoworkbench.services.localization import AppLanguage
from geoworkbench.ui.time_depth_mapping_dialog import TimeDepthMappingDialog


def make_dialog(
    language: AppLanguage = AppLanguage.RU,
) -> tuple[TimeDepthMappingDialog, ProjectSession]:
    dataset = Dataset(
        "dataset", "Log", DatasetKind.GTI, DepthDomain.MD, np.array([100.0, 110.0, 130.0])
    )
    dataset.add_index(
        DatasetIndex(
            "time",
            "TIME",
            IndexType.RELATIVE_TIME,
            IndexRole.TIME,
            "s",
            np.array([0.0, 10.0, 10.0]),
        )
    )
    session = ProjectSession()
    session.add_dataset(dataset)
    return (
        TimeDepthMappingDialog(
            dataset, TimeDepthMappingController(session), language=language
        ),
        session,
    )


def test_mapping_dialog_saves_and_resolves_profile(qapp) -> None:
    dialog, session = make_dialog()
    dialog.name_edit.setText("Повторный проход")
    dialog.policy_selector.setCurrentIndex(
        dialog.policy_selector.findData(TimeDepthAggregationPolicy.MEAN.value)
    )

    dialog._save()
    dialog.time_value_edit.setText("10")
    dialog._resolve()

    assert dialog.profile_selector.count() == 2
    assert dialog.profile_selector.currentText() == "Повторный проход"
    assert "Глубина: 120" in dialog.result_label.text()
    assert "строка: —" in dialog.result_label.text()
    assert "совпадений: 2" in dialog.result_label.text()
    assert session.dirty
    dialog.close()


def test_mapping_dialog_filters_profiles_and_localizes_english(qapp) -> None:
    dialog, session = make_dialog(AppLanguage.EN)
    controller = dialog.controller
    controller.save_profile(
        "Current dataset", "time", dialog.dataset.active_index_id, TimeDepthAggregationPolicy.FIRST
    )
    other = Dataset("other", "Other", DatasetKind.GTI, DepthDomain.MD, np.array([1.0]))
    session.current_dataset_id = other.dataset_id
    session.current_well.datasets[other.dataset_id] = other  # type: ignore[union-attr]
    session.current_dataset_id = dialog.dataset.dataset_id

    dialog._refresh_profiles()

    assert dialog.windowTitle() == "TIME↔DEPTH profiles"
    assert dialog.profile_selector.count() == 2
    assert dialog.save_button.text() == "Save"
    dialog.close()
