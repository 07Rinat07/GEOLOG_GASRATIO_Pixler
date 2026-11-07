import numpy as np
from PySide6.QtWidgets import QDialog, QPushButton

from geoworkbench.domain.models import CurveData, CurveMetadata, DatasetKind
from geoworkbench.project.external_las_insert_controller import ExternalLasInsertController
from geoworkbench.services.external_las_insert import ExternalLasCurveSelection
from geoworkbench.services.localization import AppLanguage
from geoworkbench.services.semantic_channels import SemanticChannelDictionary
from geoworkbench.ui.gis_reference_dialog import GisReferenceDialog
from test_external_las_insert_controller import dataset, imported
from test_gas_interval_gis_review_ui import _with_inserted_gis


def test_gas_interval_can_open_inserted_resistivity_without_gr_or_calculation(qapp, monkeypatch, tmp_path):
    workspace, session, receiver, combined = _with_inserted_gis(monkeypatch, tmp_path, AppLanguage.EN)
    gr_key = next(key for key, curve in combined.curves.items() if curve.metadata.original_mnemonic == "GR")
    del combined.curves[gr_key]
    for key in tuple(combined.parameters):
        if key.startswith("EXTERNAL_LAS_IMPORT_"):
            del combined.parameters[key]
    source = dataset("resistivity", [100.0, 101.0, 102.0])
    source.kind = DatasetKind.GIS
    binding = SemanticChannelDictionary().resolve("RT", unit="ohm.m")
    source.curves["rt"] = CurveData(
        CurveMetadata("rt", "RT", binding.canonical_mnemonic, "ohm.m", "Resistivity",
                      source.dataset_id, "source:las", binding),
        np.array([4.0, np.nan, 12.0]),
    )
    controller = ExternalLasInsertController(session)
    monkeypatch.setattr(
        "geoworkbench.project.external_las_insert_controller.import_las_with_report",
        lambda _path: imported(source, tmp_path / "rt.las"),
    )
    analysis = controller.analyze_file(tmp_path / "rt.las")
    controller.apply(analysis, (ExternalLasCurveSelection("rt", "RT"),))
    seen = []

    def inspect(dialog):
        key = next(key for key, curve in combined.curves.items() if curve.metadata.original_mnemonic == "RT")
        dialog.channel.setCurrentIndex(dialog.channel.findData(key))
        assert dialog.method.currentData() is None
        dialog.review_source_interval.click()
        assert dialog._t("source_interval_notice") in dialog.interval_review_label.text()
        assert dialog._t("interval_value_bounds", minimum="4", maximum="12", unit="ohm.m") in (
            dialog.interval_review_label.text()
        )
        assert dialog.sample is None
        seen.append(True)
        return QDialog.DialogCode.Rejected

    monkeypatch.setattr(GisReferenceDialog, "exec", inspect)
    try:
        workspace.geology_evidence_button.click()
        dialog = workspace._geology_evidence_dialog
        assert dialog is not None
        button = dialog.findChild(QPushButton, "interpretation-geology-review-gis")
        assert button is not None and not button.isHidden()
        button.click()
        assert seen == [True] and receiver.curves == {}
    finally:
        workspace.close()
