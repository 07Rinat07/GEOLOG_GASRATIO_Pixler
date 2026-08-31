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


def test_visible_factory_catalog_contains_only_a4_workflows() -> None:
    forms = visible_factory_forms(None, "ru")
    ids = {form.form_id for form in forms}

    assert len(forms) == 10
    assert ids.isdisjoint(HIDDEN_FACTORY_TEMPLATE_IDS)
    assert ids == {
        "factory-masterlog-a4-portrait",
        "factory-masterlog-a4-landscape",
        "factory-technology-a4-portrait",
        "factory-technology-a4-landscape",
        "factory-daily-a4-portrait",
        "factory-daily-a4-landscape",
        "factory-complex-gas-a4-portrait",
        "factory-complex-gas-a4-landscape",
        "factory-composite-log-a4-portrait",
        "factory-composite-log-a4-landscape",
    }


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
