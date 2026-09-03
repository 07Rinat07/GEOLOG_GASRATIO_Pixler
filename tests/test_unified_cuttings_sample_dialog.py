from __future__ import annotations

from geoworkbench.domain.models import CuttingsComponent, CuttingsSample
from geoworkbench.project.lithotype_catalog_models import CatalogLithotype
from geoworkbench.services.localization import AppLanguage
from geoworkbench.ui.unified_cuttings_sample_dialog import UnifiedCuttingsSampleDialog


def test_existing_composition_is_registered_before_combo_signal_fires(qapp) -> None:
    del qapp
    lithotype = CatalogLithotype(
        lithotype_id="sandstone",
        code="SS",
        name_ru="Песчаник",
        name_en="Sandstone",
        category="sedimentary",
        color="#d6b36a",
        pattern_key="sandstone",
        system=True,
    )
    sample = CuttingsSample(
        sample_id="sample-existing",
        top_depth=1980.0,
        bottom_depth=1981.0,
        components=[CuttingsComponent(lithotype_id="sandstone", percentage=100.0)],
    )

    dialog = UnifiedCuttingsSampleDialog(
        sample.top_depth,
        sample.bottom_depth,
        (lithotype,),
        language=AppLanguage.RU,
        sample=sample,
    )

    assert dialog.rock_inputs[0].currentData() == "sandstone"
    assert dialog.percent_inputs[0].value() == 100.0
    assert dialog.components() == {"sandstone": 100.0}
