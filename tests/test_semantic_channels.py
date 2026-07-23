from __future__ import annotations

from geoworkbench.services.semantic_channels import SemanticChannelDictionary
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
