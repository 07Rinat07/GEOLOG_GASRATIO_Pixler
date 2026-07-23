from __future__ import annotations

import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_import_review_ui_exists_and_does_not_touch_project_session() -> None:
    source = (ROOT / "src/geoworkbench/ui/import_review_dialog.py").read_text(
        encoding="utf-8"
    )

    assert "class ImportReviewDialog(QDialog):" in source
    assert "ImportReviewController" in source
    assert "self.controller.preview(" in source
    assert "self.controller.commit(" in source
    assert source.count("itemChanged.connect(self._include_changed)") == 1
    assert "ProjectSession" not in source
    assert ".add_dataset(" not in source
    assert ".dirty" not in source


def test_all_import_sources_use_one_review_callback_before_registration() -> None:
    jobs = (ROOT / "src/geoworkbench/services/import_jobs.py").read_text(
        encoding="utf-8"
    )
    window = (ROOT / "src/geoworkbench/ui/main_window.py").read_text(
        encoding="utf-8"
    )

    assert jobs.count("self._review_or_original(") == 4
    assert window.count("review_dataset=self._review_imported_dataset") == 4
    assert "ImportReviewDialog(" in window


def test_import_review_localization_keys_are_complete_and_synchronized() -> None:
    catalogs: dict[str, dict[str, str]] = {}
    for language in ("ru", "kk", "en"):
        path = ROOT / "src/geoworkbench/resources/i18n" / f"{language}.json"
        catalogs[language] = json.loads(path.read_text(encoding="utf-8"))

    assert set(catalogs["ru"]) == set(catalogs["kk"]) == set(catalogs["en"])
    review_keys = {key for key in catalogs["ru"] if key.startswith("import_review.")}
    assert len(review_keys) >= 80
    for language, catalog in catalogs.items():
        assert all(catalog[key].strip() for key in review_keys), language
        assert catalog["import_review.title"] != "import_review.title"
