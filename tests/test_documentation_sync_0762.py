from pathlib import Path

from tools.check_documentation import (
    audit_compact_column_coverage,
    audit_current_documentation_contract,
    audit_daily_project_workflow_coverage,
    audit_documentation_hygiene,
    audit_documentation_navigation,
    audit_form_creation_naming_coverage,
    audit_i18n_key_parity,
    audit_localized_document_structure,
    audit_localized_file_parity,
    audit_markdown_links,
    audit_project_lifecycle_contract,
    audit_runtime_contract,
    audit_startup_command_contract,
    audit_user_workflow_coverage,
    audit_version_contract,
)

ROOT = Path(__file__).resolve().parents[1]


def _write_valid_project_lifecycle_docs(root: Path) -> None:
    content = {
        "ru": (
            "# Рабочий процесс\n\nИсточник LAS, проект `.geologpkg` и экспорт LAS — "
            "разные объекты. GS2 и Paradox используют единый экспорт. При закрытии "
            "dirty-сессии защита предлагает сохранить проект или отменить действие.\n",
            "# Сохранение\n\nИсходный файл, проект и экспорт разделены. Если есть "
            "несохранённые изменения, при закрытии предлагаются четыре действия: "
            "Сохранить проект, Экспортировать LAS-копию, Не сохранять и Отмена. "
            "GS2 и Paradox используют единый экспорт.\n",
        ),
        "kk": (
            "# Жұмыс реті\n\nLAS дереккөзі, `.geologpkg` жобасы және LAS экспорты — "
            "бөлек нысандар. GS2 және Paradox бірыңғай экспортты қолданады. Dirty-сеанс "
            "жабылғанда қорғаныс жобаны сақтауды немесе әрекетті болдырмауды ұсынады.\n",
            "# Сақтау\n\nБастапқы дереккөз, жоба және экспорт бөлек. Сақталмаған "
            "өзгерістер болса, жабу кезінде төрт әрекет ұсынылады: Жобаны сақтау, "
            "LAS көшірмесін экспорттау, Сақтамау және Болдырмау. GS2 және Paradox "
            "бірыңғай экспортты қолданады.\n",
        ),
        "en": (
            "# Workflow\n\nThe source LAS, `.geologpkg` project, and LAS export are "
            "different objects. GS2 and Paradox use the same export path. When a dirty "
            "session closes, the guard offers to save the project or cancel.\n",
            "# Saving\n\nSource data, the project, and export are separate. When there "
            "are unsaved changes, closing offers four actions: Save project, Export LAS "
            "copy, Don't save, and Cancel. GS2 and Paradox use the same export path.\n",
        ),
    }
    for language, (workflow, saving) in content.items():
        directory = root / "docs" / language
        directory.mkdir(parents=True)
        (directory / "PROJECT_WORKFLOW.md").write_text(workflow, encoding="utf-8")
        (directory / "SESSION_SAVING.md").write_text(saving, encoding="utf-8")


def test_localized_document_sets_are_identical() -> None:
    """A user-facing document may not exist in only one or two languages."""

    assert audit_localized_file_parity(ROOT) == []



def test_current_localized_guides_have_comparable_structure() -> None:
    """A translated current guide must not be only a shortened placeholder."""

    assert audit_localized_document_structure(ROOT) == []


def test_documentation_tree_contains_only_current_sources() -> None:
    """Generated reports and parallel plans must stay out of the documentation tree."""

    assert audit_documentation_hygiene(ROOT) == []


def test_documentation_hygiene_rejects_generated_and_parallel_sources(
    tmp_path: Path,
) -> None:
    """The hygiene gate must reject every removed document category."""

    docs = tmp_path / "docs"
    localized = docs / "ru"
    validation = docs / "validation"
    localized.mkdir(parents=True)
    validation.mkdir()

    (docs / "PROJECT_PLAN.md").write_text("# Canonical plan\n", encoding="utf-8")
    (
        validation / "ETP12_INTEROPERABILITY_MATRIX_TEMPLATE.csv"
    ).write_text("scenario,status\n", encoding="utf-8")
    forbidden = (
        docs / "RELEASE_NOTES_0.7.93.md",
        docs / "BUILD_MANIFEST_0.7.93.md",
        docs / "HOTFIX_REPORT_0.7.93.md",
        docs / "IMPLEMENTATION_REPORT_0.7.93.md",
        docs / "INCREMENT_0.7.md",
        localized / "PROJECT_PLAN.md",
        docs / "PRODUCT_AUDIT_2026.md",
        docs / "PROJECT_STATUS.md",
        docs / "ROADMAP.md",
        validation / "render.png",
        docs / "LAS_curve_zero_validation_0.7.87.json",
    )
    for path in forbidden:
        path.write_text("generated\n", encoding="utf-8")

    issues = audit_documentation_hygiene(tmp_path)
    rejected = {
        issue.message.split(" is forbidden:", 1)[0]
        for issue in issues
    }
    assert rejected == {
        path.relative_to(tmp_path).as_posix()
        for path in forbidden
    }


def test_all_internal_markdown_links_resolve() -> None:
    """Documentation navigation must not lead to missing local files."""

    assert audit_markdown_links(ROOT) == []


def test_all_documents_are_reachable_from_the_canonical_index() -> None:
    """No current guide or engineering contract may become an orphan."""

    assert audit_documentation_navigation(ROOT) == []


def test_navigation_audit_rejects_an_orphan_document(tmp_path: Path) -> None:
    """The canonical index must lead to every Markdown document."""

    docs = tmp_path / "docs"
    docs.mkdir()
    (docs / "DOCUMENTATION_INDEX.md").write_text(
        "# Index\n\n[Current](CURRENT.md)\n",
        encoding="utf-8",
    )
    (docs / "CURRENT.md").write_text("# Current\n", encoding="utf-8")
    orphan = docs / "ORPHAN.md"
    orphan.write_text("# Orphan\n", encoding="utf-8")

    issues = audit_documentation_navigation(tmp_path)
    assert [issue.message for issue in issues] == [
        "docs/ORPHAN.md is not reachable from docs/DOCUMENTATION_INDEX.md"
    ]


def test_interface_translation_keys_are_synchronized() -> None:
    """Stable interface keys must be present in RU, KK, and EN catalogs."""

    assert audit_i18n_key_parity(ROOT) == []


def test_package_metadata_uses_one_version() -> None:
    """Package metadata must expose one version without per-build documents."""

    assert audit_version_contract(ROOT) == []


def test_current_runtime_contract_matches_source_constants() -> None:
    """Canonical architecture and plan may not advertise stale schema versions."""

    assert audit_runtime_contract(ROOT) == []


def test_guides_cover_save_reopen_and_catalog_symbols() -> None:
    """The complete symbol lifecycle must remain documented in every language."""

    assert audit_user_workflow_coverage(ROOT) == []


def test_guides_cover_portable_project_daily_append_and_three_languages() -> None:
    """The main guides must retain the safe daily .geologpkg workflow."""

    assert audit_daily_project_workflow_coverage(ROOT) == []


def test_project_lifecycle_guides_match_the_current_ui_contract() -> None:
    """Source/project/export and dirty-close behavior must stay explicit in every language."""

    assert audit_project_lifecycle_contract(ROOT) == []


def test_project_lifecycle_audit_rejects_stale_inner_export_guidance(
    tmp_path: Path,
) -> None:
    """A removed GS2 exporter limitation may not return under another line wrap."""

    _write_valid_project_lifecycle_docs(tmp_path)
    path = tmp_path / "docs" / "en" / "PROJECT_WORKFLOW.md"
    path.write_text(
        path.read_text(encoding="utf-8")
        + "The GS2 path does not propagate its inner Save LAS action.\n",
        encoding="utf-8",
    )

    issues = audit_project_lifecycle_contract(tmp_path)

    assert [issue.message for issue in issues] == [
        "docs/en/PROJECT_WORKFLOW.md contains stale guidance: "
        "does not propagate its inner"
    ]


def test_project_lifecycle_audit_rejects_stale_close_prompt_guidance(
    tmp_path: Path,
) -> None:
    """Current guides may not deny the dirty-close prompt that the application provides."""

    _write_valid_project_lifecycle_docs(tmp_path)
    path = tmp_path / "docs" / "ru" / "FEATURES.md"
    path.write_text(
        "# Возможности\n\n"
        "Текущая версия не гарантирует запрос на сохранение при закрытии.\n",
        encoding="utf-8",
    )

    issues = audit_project_lifecycle_contract(tmp_path)

    assert [issue.message for issue in issues] == [
        "docs/ru/FEATURES.md contains stale guidance: "
        "не гарантирует запрос на сохранение при закрытии"
    ]


def test_project_lifecycle_audit_rejects_stale_no_autosave_guidance(
    tmp_path: Path,
) -> None:
    """Daily append autosave and recovery must not be documented as absent."""

    _write_valid_project_lifecycle_docs(tmp_path)
    path = tmp_path / "docs" / "en" / "PROJECT_WORKFLOW.md"
    path.write_text(
        path.read_text(encoding="utf-8")
        + "Dependable autosave is not available yet.\n",
        encoding="utf-8",
    )

    issues = audit_project_lifecycle_contract(tmp_path)

    assert [issue.message for issue in issues] == [
        "docs/en/PROJECT_WORKFLOW.md contains stale guidance: "
        "dependable autosave is not available yet"
    ]


def test_guides_cover_compact_columns_and_embedded_user_template() -> None:
    """All three languages must explain widths, migration, and the built-in template."""

    assert audit_compact_column_coverage(ROOT) == []


def test_guides_cover_visible_library_and_duplicate_name_protection() -> None:
    """Creation instructions must show how to review and name forms in every language."""

    assert audit_form_creation_naming_coverage(ROOT) == []


def test_documented_startup_command_matches_module_entrypoint() -> None:
    """README and localized guides must use the executable module command."""

    assert audit_startup_command_contract(ROOT) == []


def test_current_index_and_testing_guide_use_canonical_entry_points() -> None:
    """Current documentation navigation must point to canonical documents."""

    assert audit_current_documentation_contract(ROOT) == []


def test_i18n_audit_rejects_invalid_values_and_placeholders(tmp_path) -> None:
    import json

    directory = tmp_path / "src/geoworkbench/resources/i18n"
    directory.mkdir(parents=True)
    catalogs = {
        "ru": {"depth": "Глубина {depth}", "empty": "ok", "broken": "ok"},
        "kk": {"depth": "Тереңдік {depth}", "empty": " ", "broken": "{"},
        "en": {"depth": "Depth {value}", "empty": 42, "broken": "ok"},
    }
    for language, catalog in catalogs.items():
        (directory / f"{language}.json").write_text(json.dumps(catalog), encoding="utf-8")
    issues = audit_i18n_key_parity(tmp_path)
    assert len(issues) == 4
    assert sum(issue.category == "i18n-values" for issue in issues) == 2
    assert sum(issue.category == "i18n-format" for issue in issues) == 2



def test_fusion_lithology_guides_describe_explicit_sources_and_unknown_state() -> None:
    for language in ("ru", "kk", "en"):
        guide = (ROOT / "docs" / language / "NORMALIZED_GAS_INTERPRETATION.md").read_text(
            encoding="utf-8",
        )
        for name in ("`review_gis_gti_lithology_intervals`", "`LithologyObservation`",
                     "UNKNOWN_OR_MIXED", "ObservationQuality", "VALIDATED", "shortlist"):
            assert name in guide


def test_fusion_md_partition_guides_describe_both_review_contracts() -> None:
    for language in ("ru", "kk", "en"):
        guide = (ROOT / "docs" / language / "NORMALIZED_GAS_INTERPRETATION.md").read_text(
            encoding="utf-8",
        )
        for name in ("`review_gis_gti_intervals`", "`review_gis_gti_interval`",
                     "INTERP-FUSION-01", "Source IDs", "suspect/rejected", "MD/lag"):
            assert name in guide


def test_petrophysical_reference_guides_keep_methods_and_operator_scope_in_sync() -> None:
    """Three guides describe the same methods, examples and bounded operator workflow."""

    names = (
        "gamma_ray_index",
        "density_porosity",
        "archie_water_saturation",
        "igr-linear-1",
        "density-porosity-1",
        "archie-water-saturation-1",
        "outside_reference_range",
        "outside_physical_range",
        "GR=65",
        "IGR=0.4",
        "rho_bulk=2.42",
        "phiD≈0.16959",
        "phi=0.2",
        "Sw=0.5",
        "ValueError",
        "LAS",
        "MD/TVD",
        "PR #686",
        "review_gis_reference_input",
        "ready_for_calibration",
        "create_gis_reference_calibration",
        "GisReferenceDialog",
        "petro_reference.action",
        "evaluate_gis_reference_sample",
        "applicability_reference",
        "curve.version",
        "curve_key",
        "kg/m3",
        "uR/h",
    )
    detail_headings = {
        "ru": "Сохранённые реквизиты источника",
        "kk": "Дереккөздің сақталған деректемелері",
        "en": "Saved source details",
    }
    for language, heading in detail_headings.items():
        guide = (
            ROOT / "docs" / language / "PETROPHYSICAL_REFERENCE_MODELS.md"
        ).read_text(encoding="utf-8")
        assert all(name in guide for name in names)
        assert guide.count("\n## ") == 7
        assert guide.count(f"\n## {heading}\n") == 1

    index = (ROOT / "docs" / "DOCUMENTATION_INDEX.md").read_text(encoding="utf-8")
    for language in ("ru", "kk", "en"):
        assert f"{language}/PETROPHYSICAL_REFERENCE_MODELS.md" in index

def test_florovskaya_residual_ring_guides_remain_in_sync_in_three_languages() -> None:
    """Operator instructions and UI must describe the same 1–5 LBA quantity scale."""

    required: dict[str, tuple[str, str, str]] = {
        "ru": ("Прерывистое кольцо", "2", "ЛБА: люминесцирующее пятно"),
        "kk": ("Үзік сақина", "2", "ЛБА: люминесценттік дақ"),
        "en": ("Broken (discontinuous) ring", "2", "LBA fluorescence-spot"),
    }
    for language, (ring, score, label) in required.items():
        late = (ROOT / "docs" / language / "LATE_ANALYSIS_UPDATE.md").read_text(
            encoding="utf-8"
        )
        gas = (
            ROOT / "docs" / language / "NORMALIZED_GAS_INTERPRETATION.md"
        ).read_text(encoding="utf-8")
        for document in (late, gas):
            assert "lba_intensity" in document
            assert score in document
        assert ring in late
        assert label in (
            ROOT / "src" / "geoworkbench" / "resources" / "i18n"
            / f"{language}.json"
        ).read_text(encoding="utf-8")


def test_lithology_history_selection_is_documented_in_three_languages() -> None:
    for language in ("ru", "kk", "en"):
        guide = (ROOT / "docs" / language / "NORMALIZED_GAS_INTERPRETATION.md").read_text(
            encoding="utf-8",
        )
        assert "load_lithology_review_history" in guide
        assert "1–16" in guide


def test_lithology_archival_reader_is_documented_in_three_languages() -> None:
    for language in ("ru", "kk", "en"):
        guide = (ROOT / "docs" / language / "NORMALIZED_GAS_INTERPRETATION.md").read_text(
            encoding="utf-8",
        )
        assert "SavedLithologyReview" in guide
        assert "schema v1" in guide


def test_lithology_review_export_describes_unapproved_record_in_three_languages() -> None:
    for language in ("ru", "kk", "en"):
        guide = (ROOT / "docs" / language / "NORMALIZED_GAS_INTERPRETATION.md").read_text(
            encoding="utf-8",
        )
        assert "schema_version=1" in guide
        assert "operator_review_not_geological_approval" in guide


def test_lithology_mapping_dialog_is_documented_in_three_languages() -> None:
    for language in ("ru", "kk", "en"):
        guide = (ROOT / "docs" / language / "NORMALIZED_GAS_INTERPRETATION.md").read_text(
            encoding="utf-8",
        )
        assert "LithologyMappingDialog" in guide


def test_lithology_source_mapping_contract_in_three_languages() -> None:
    for language in ("ru", "kk", "en"):
        guide = (ROOT / "docs" / language / "NORMALIZED_GAS_INTERPRETATION.md").read_text(
            encoding="utf-8",
        )
        for token in (
            "review_lithology_source", "create_lithology_mapping",
            "evaluate_lithology_mapping", "mapping_id", "reviewer",
            "applicability_reference", "session-local data-only",
        ):
            assert token in guide


def test_florovskaya_status_and_instructions_use_single_canonical_plan() -> None:
    """Require one source of truth, with multilingual operator guidance."""

    policy = (ROOT / "docs" / "DOCUMENTATION_POLICY.md").read_text(
        encoding="utf-8"
    )
    plan = (ROOT / "docs" / "PROJECT_PLAN.md").read_text(encoding="utf-8")
    assert "docs/PROJECT_PLAN.md" in policy
    assert "docs/ru" in policy
    assert "docs/kk" in policy
    assert "docs/en" in policy
    assert "DOCUMENTATION_POLICY.md" in plan
    assert "docs/{ru,kk,en}" in plan
