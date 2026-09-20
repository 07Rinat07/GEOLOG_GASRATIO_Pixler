from __future__ import annotations

from dataclasses import FrozenInstanceError, replace
from pathlib import Path

import pytest

from geoworkbench.services.semantic_channels import SemanticChannelDictionary, SemanticContext
from geoworkbench.services.uom_dictionary import QuantityClass


def test_resolver_preserves_source_mnemonic_and_attaches_sensor_provenance() -> None:
    binding = SemanticChannelDictionary().resolve(
        "ROP",
        description="Rate of penetration",
        unit="м/ч",
        source_mnemonic="Vendor_ROP_01",
    )

    assert binding.canonical_kind == "drilling.rop"
    assert binding.canonical_mnemonic == "ROP"
    assert binding.quantity_class is QuantityClass.LINEAR_VELOCITY
    assert binding.canonical_uom == "m/h"
    assert binding.source_uom == "м/ч"
    assert binding.source_mnemonic == "Vendor_ROP_01"
    assert binding.sensor_id == "editor_gid_106"
    assert binding.source == "Editor/Sensors.DB"
    assert binding.confidence == 1.0
    assert binding.resolved is True


def test_legacy_s_code_is_resolved_through_existing_sensor_catalog() -> None:
    binding = SemanticChannelDictionary().resolve("S200", unit="т")

    assert binding.canonical_mnemonic == "HKLD"
    assert binding.canonical_kind == "drilling.hkld"
    assert binding.sensor_id == "editor_gid_200"
    assert binding.matched_by == "sensor_legacy_gid"


def test_explicit_canonical_hint_is_preserved_for_existing_project_decision() -> None:
    binding = SemanticChannelDictionary().resolve(
        "CH4",
        unit="%",
        canonical_mnemonic="C1_CUSTOM",
    )

    assert binding.canonical_mnemonic == "C1_CUSTOM"
    assert binding.canonical_kind == "gas.c1"
    assert "canonical_hint" in binding.matched_by
    assert any("catalog suggested" in item for item in binding.evidence)


def test_unknown_channel_is_not_guessed_and_keeps_vendor_unit() -> None:
    binding = SemanticChannelDictionary().resolve("X_VENDOR_77", unit="ticks")

    assert binding.canonical_kind == "unknown.x_vendor_77"
    assert binding.canonical_mnemonic == "X_VENDOR_77"
    assert binding.quantity_class is QuantityClass.UNKNOWN
    assert binding.canonical_uom == "ticks"
    assert binding.sensor_id is None
    assert binding.confidence == 0.0
    assert binding.resolved is False


def test_resolver_reports_quantity_conflict_without_discarding_sensor_match() -> None:
    binding = SemanticChannelDictionary().resolve("C1", unit="psi")

    assert binding.canonical_kind == "gas.c1"
    assert binding.quantity_class is QuantityClass.VOLUME_FRACTION
    assert binding.confidence == 0.75
    assert binding.resolved is True
    assert any("quantity conflicts" in item for item in binding.evidence)

def test_semantic_context_is_immutable_and_pins_catalog_version() -> None:
    dictionary = SemanticChannelDictionary()
    context = dictionary.context(
        source_mnemonic="Vendor_ROP_01",
        mapped_mnemonic="ROP",
        source_uom="м/ч",
        description="Rate of penetration",
        mapping_evidence=("las_curve_index=3",),
    )

    assert isinstance(context, SemanticContext)
    assert context.source_mnemonic == "Vendor_ROP_01"
    assert context.mapped_mnemonic == "ROP"
    assert context.source_uom == "м/ч"
    assert context.mapping_evidence == ("las_curve_index=3",)
    assert context.catalog_version == dictionary.catalog_version
    assert context.catalog_version.startswith("sensors-v1:")

    with pytest.raises(FrozenInstanceError):
        context.source_mnemonic = "changed"  # type: ignore[misc]


def test_resolve_context_preserves_importer_evidence_and_catalog_version() -> None:
    dictionary = SemanticChannelDictionary()
    context = dictionary.context(
        source_mnemonic="Vendor_ROP_01",
        mapped_mnemonic="ROP",
        source_uom="м/ч",
        mapping_evidence=("source_column=7", "profile=vendor-a"),
    )

    binding = dictionary.resolve_context(context)

    assert binding.source_mnemonic == "Vendor_ROP_01"
    assert binding.canonical_mnemonic == "ROP"
    assert "source_column=7" in binding.evidence
    assert "profile=vendor-a" in binding.evidence
    assert f"catalog_version={dictionary.catalog_version}" in binding.evidence


def test_resolve_context_rejects_context_from_different_catalog_version() -> None:
    dictionary = SemanticChannelDictionary()
    context = dictionary.context(source_mnemonic="ROP")

    with pytest.raises(ValueError, match="catalog_version"):
        dictionary.resolve_context(replace(context, catalog_version="sensors-v1:stale"))


def test_legacy_resolve_api_matches_context_resolution() -> None:
    dictionary = SemanticChannelDictionary()

    legacy = dictionary.resolve(
        "ROP",
        description="Rate of penetration",
        unit="м/ч",
        source_mnemonic="Vendor_ROP_01",
    )
    context = dictionary.context(
        source_mnemonic="Vendor_ROP_01",
        mapped_mnemonic="ROP",
        source_uom="м/ч",
        description="Rate of penetration",
    )
    contextual = dictionary.resolve_context(context)

    assert legacy == contextual


def test_las_import_uses_semantic_context_boundary() -> None:
    source = Path("src/geoworkbench/data/las_adapter.py").read_text(encoding="utf-8")

    assert "semantic_dictionary.context(" in source
    assert "mapping_evidence=(f\"las_curve_index={curve_index}\",)" in source
    assert "semantic_dictionary.resolve_context(semantic_context)" in source

