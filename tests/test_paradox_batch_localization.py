import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
CATALOG_DIR = ROOT / "src/geoworkbench/resources/i18n"


REQUIRED_KEYS = {
    "paradox.batch_instructions",
    "paradox.open_result_folder",
    "paradox.open_selected_las",
    "paradox.convert_and_save",
    "paradox.stop_conversion",
    "paradox.batch_duplicate_targets",
    "paradox.batch_done_summary",
    "paradox.batch_where_results",
    "paradox.confirm_cancel_close",
    "paradox.status_configuration_required",
    "paradox.apply_batch_settings",
    "paradox.configure_selected_source",
    "paradox.retry_after_configuration",
    "paradox.batch_configuration_summary",
}


def _catalog(language: str) -> dict[str, str]:
    return json.loads((CATALOG_DIR / f"{language}.json").read_text(encoding="utf-8"))


def test_batch_workflow_text_exists_in_all_languages() -> None:
    catalogs = {language: _catalog(language) for language in ("ru", "kk", "en")}
    for catalog in catalogs.values():
        assert REQUIRED_KEYS <= set(catalog)
        assert all(catalog[key].strip() for key in REQUIRED_KEYS)


def test_duplicate_target_text_keeps_recommended_mask_literal() -> None:
    values = {"target": "same.las", "first": "a.db", "second": "b.db"}
    for language in ("ru", "kk", "en"):
        rendered = _catalog(language)["paradox.batch_duplicate_targets"].format(**values)
        assert "{source_name}_{mode}.las" in rendered
