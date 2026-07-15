from geoworkbench.data.las_export_plan import LasExportPlan, LasExportVersion
from geoworkbench.ui.las_export_dialog import LasExportPlanDialog


def test_las_export_dialog_round_trips_plan(qapp) -> None:
    initial = LasExportPlan(
        version=LasExportVersion.V1_2,
        wrap=True,
        null_value=-999.25,
        precision=7,
        preserve_custom_sections=False,
    )

    dialog = LasExportPlanDialog(initial=initial)

    assert dialog.export_plan() == initial
