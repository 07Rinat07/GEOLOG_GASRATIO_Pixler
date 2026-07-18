import numpy as np
from PySide6.QtWidgets import QDialog

from geoworkbench.domain.models import Dataset, DatasetKind, DepthDomain
from geoworkbench.project.masterlog_template_controller import MasterlogTemplateController
from geoworkbench.project.session import ProjectSession
from geoworkbench.services.localization import AppLanguage
from geoworkbench.ui.masterlog_curve_mapping_dialog import MasterlogCurveMappingDialog


def test_masterlog_curve_mapping_dialog_maps_foreign_las_curves(qapp) -> None:
    session = ProjectSession()
    controller = MasterlogTemplateController(session)
    template = controller.create("Customer")
    controller.add_column(
        template.template_id,
        title="Gas",
        column_type="curves",
        width_mm=40.0,
        curve_mnemonics=["TG", "C1"],
    )
    dataset = Dataset("foreign", "Vendor", DatasetKind.GTI, DepthDomain.MD, np.array([1.0]))
    total = dataset.upsert_curve("TOTAL_GAS_X", np.array([100.0]))
    methane = dataset.upsert_curve("METHANE_X", np.array([80.0]))
    dialog = MasterlogCurveMappingDialog(
        controller, template.template_id, dataset, language=AppLanguage.EN
    )
    dialog.selectors["TG"].setCurrentIndex(dialog.selectors["TG"].findData(total.metadata.curve_id))
    dialog.selectors["C1"].setCurrentIndex(
        dialog.selectors["C1"].findData(methane.metadata.curve_id)
    )

    dialog._save()

    assert dialog.result() == QDialog.DialogCode.Accepted
    assert controller.curve_bindings(template.template_id, dataset) == {
        "TG": total.metadata.curve_id,
        "C1": methane.metadata.curve_id,
    }
