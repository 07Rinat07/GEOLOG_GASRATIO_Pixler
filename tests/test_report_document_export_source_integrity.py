from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_docx_and_html_use_one_resolved_report_and_output_transaction() -> None:
    source = (ROOT / "src/geoworkbench/ui/main_window.py").read_text(encoding="utf-8")
    block = source[
        source.index("    def _export_selected_table(") : source.index(
            "    def _build_tabular_report_passport("
        )
    ]

    assert '"docx": (".docx", "Word (*.docx)")' in block
    assert '"html": (".html", "HTML (*.html)")' in block
    assert "export_resolved_report_docx(" in block
    assert "export_resolved_report_html(" in block
    assert "execute_report_output_transaction(" in block
    assert "resolved_report" in block


def test_document_adapters_do_not_import_qt_or_re_resolve_report() -> None:
    source = (ROOT / "src/geoworkbench/data/report_document_export.py").read_text(
        encoding="utf-8"
    )

    assert "PySide6" not in source
    assert "resolve_report_definition" not in source
    assert "report.interval.indices" in source
    assert "report.coverage" in source
    assert "zipfile.ZipFile" in source


def test_docx_html_actions_are_localized_in_all_catalogs() -> None:
    import json

    catalogs = {
        language: json.loads(
            (ROOT / f"src/geoworkbench/resources/i18n/{language}.json").read_text(
                encoding="utf-8"
            )
        )
        for language in ("ru", "kk", "en")
    }
    assert set(catalogs["ru"]) == set(catalogs["kk"]) == set(catalogs["en"])
    keys = {
        "selection_export.docx_action",
        "selection_export.html_action",
        "selection_export.unsupported_format",
    }
    for catalog in catalogs.values():
        assert keys <= set(catalog)
        assert all(catalog[key].strip() for key in keys)
