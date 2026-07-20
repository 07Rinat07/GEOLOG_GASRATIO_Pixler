from geoworkbench.domain.models import CuttingsComponent, CuttingsSample
from geoworkbench.project.lithotype_catalog_controller import CatalogLithotype
from geoworkbench.services.localization import AppLanguage
from geoworkbench.ui.masterlog_interval_fill_dialog import CuttingsCompositionDialog


def _catalog() -> tuple[CatalogLithotype, ...]:
    return (
        CatalogLithotype(
            "sandstone",
            "SS",
            "Песчаник",
            "Sandstone",
            "sedimentary",
            "#e7cf8b",
            "dots",
            True,
            "Құмтас",
        ),
        CatalogLithotype(
            "clay",
            "CL",
            "Глина",
            "Clay",
            "sedimentary",
            "#94a3b8",
            "horizontal",
            True,
            "Саз",
        ),
    )


def test_cuttings_edit_dialog_prefills_interval_and_percentages(qapp) -> None:
    sample = CuttingsSample(
        "sample",
        100.0,
        105.0,
        [CuttingsComponent("sandstone", 70.0), CuttingsComponent("clay", 30.0)],
        lba_type_id="ЛБ",
        calcite_percent=50.0,
        description="Preserve me",
    )
    dialog = CuttingsCompositionDialog(
        sample.top_depth,
        sample.bottom_depth,
        _catalog(),
        language=AppLanguage.RU,
        sample=sample,
    )

    assert dialog.windowTitle() == "Редактирование пробы шлама"
    assert dialog.top_depth == 100.0
    assert dialog.bottom_depth == 105.0
    assert dialog.components() == {"sandstone": 70.0, "clay": 30.0}
    dialog.close()


def test_cuttings_edit_dialog_allows_interval_correction(qapp) -> None:
    dialog = CuttingsCompositionDialog(
        100.0,
        105.0,
        _catalog(),
        language=AppLanguage.EN,
    )
    dialog.top_input.setValue(101.0)
    dialog.bottom_input.setValue(108.0)

    assert dialog.top_depth == 101.0
    assert dialog.bottom_depth == 108.0
    dialog.close()
