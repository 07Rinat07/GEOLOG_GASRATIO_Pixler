from __future__ import annotations

from pathlib import Path

from geoworkbench.forms.catalog import (
    HIDDEN_FACTORY_TEMPLATE_IDS,
    complete_form_catalog,
    visible_factory_forms,
)
from geoworkbench.forms.models import FormAxisKind, FormDocument
from geoworkbench.forms.repository import FormRepository


ROOT = Path(__file__).resolve().parents[1]


def test_visible_factory_catalog_contains_only_curated_workflows() -> None:
    forms = visible_factory_forms(None, "ru")
    ids = {form.form_id for form in forms}

    assert len(forms) == 7
    assert ids.isdisjoint(HIDDEN_FACTORY_TEMPLATE_IDS)
    assert "factory-geodata-depth-workspace" in ids
    assert "factory-engineering-control-time" in ids
    assert "factory-lithology-cuttings" in ids
    assert "factory-drilling-technology" in ids
    assert "factory-gas-ratio-pixler-depth" in ids
    assert "factory-complex-gas-analysis" in ids
    assert "factory-gas-ratio-pixler-time" in ids
    assert "factory-calcimetry" not in ids
    assert "factory-lba" not in ids


def test_complete_catalog_combines_same_factory_set_with_repository_forms(
    tmp_path: Path,
) -> None:
    repository = FormRepository(tmp_path / "forms")
    user_form = FormDocument.create("Моя форма", FormAxisKind.DEPTH)
    repository.save(user_form)

    factory = visible_factory_forms(None, "ru")
    complete = complete_form_catalog(repository, None, "ru")

    assert [form.form_id for form in complete[: len(factory)]] == [form.form_id for form in factory]
    assert complete[-1].form_id == user_form.form_id


def test_browse_and_save_workflows_use_authoritative_catalog_source() -> None:
    manager_source = (ROOT / "src/geoworkbench/ui/form_manager_dialog.py").read_text(
        encoding="utf-8"
    )
    main_source = (ROOT / "src/geoworkbench/ui/main_window.py").read_text(encoding="utf-8")

    assert "return list(visible_factory_forms(self.dataset, self.language))" in manager_source
    assert "complete_form_catalog(self.repository, self.dataset, self.language)" in manager_source
    assert "catalog = complete_form_catalog(" in main_source
    assert "CURATED_FACTORY_TEMPLATE_IDS" not in manager_source
