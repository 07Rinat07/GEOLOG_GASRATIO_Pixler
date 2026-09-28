from geoworkbench.services.las_geology_dialect import (
    GeologyChannelRole,
    normalize_geology_mnemonic,
    resolve_geology_channel,
)


def test_normalize_geology_mnemonic_handles_case_spacing_and_punctuation() -> None:
    assert normalize_geology_mnemonic("  CaCO3_(Кальцит) ") == "CACO3_КАЛЬЦИТ"


def test_resolver_accepts_canonical_and_localized_geology_aliases() -> None:
    cases = {
        "LITHOLOGY_CODE": GeologyChannelRole.PRIMARY_LITHOLOGY,
        "КОД_ПОРОДЫ": GeologyChannelRole.PRIMARY_LITHOLOGY,
        "CACO3": GeologyChannelRole.CALCITE,
        "КАРБОНАТНОСТЬ": GeologyChannelRole.LEGACY_CARBONATE,
        "DOLO": GeologyChannelRole.DOLOMITE,
        "ЛБА_ГРУППА": GeologyChannelRole.LBA_GROUP,
        "LBA_COLOUR": GeologyChannelRole.LBA_COLOR,
        "СТРАТ_КОД": GeologyChannelRole.STRATIGRAPHY_CODE,
        "DESCRIPTION_ID": GeologyChannelRole.DESCRIPTION_ID,
    }
    for mnemonic, role in cases.items():
        match = resolve_geology_channel(mnemonic)
        assert match is not None
        assert match.role is role
        assert match.slot is None
        assert match.matched_by == "mnemonic_alias"


def test_resolver_accepts_common_cuttings_slot_variants() -> None:
    rock = resolve_geology_channel("ROCK1_CODE")
    pct = resolve_geology_channel("LITHOLOGY_5_PERCENTAGE")
    russian = resolve_geology_channel("ПОРОДА3_КОЛИЧ")

    assert rock is not None
    assert rock.role is GeologyChannelRole.CUTTINGS_CODE
    assert rock.slot == 1
    assert pct is not None
    assert pct.role is GeologyChannelRole.CUTTINGS_AMOUNT
    assert pct.slot == 5
    assert russian is not None
    assert russian.role is GeologyChannelRole.CUTTINGS_AMOUNT
    assert russian.slot == 3


def test_resolver_uses_description_and_uom_only_for_strong_evidence() -> None:
    calcite = resolve_geology_channel(
        "VENDOR_77",
        description="Laboratory calcite CaCO3 content",
        unit="PCT",
    )
    strat = resolve_geology_channel(
        "X92",
        description="Stratigraphy code",
        unit="CODE",
    )
    lba = resolve_geology_channel(
        "ANALYSIS_5",
        description="ЛБА интенсивность",
        unit="CODE",
    )

    assert calcite is not None
    assert calcite.role is GeologyChannelRole.CALCITE
    assert calcite.matched_by == "description+uom"
    assert strat is not None
    assert strat.role is GeologyChannelRole.STRATIGRAPHY_CODE
    assert lba is not None
    assert lba.role is GeologyChannelRole.LBA_INTENSITY


def test_resolver_does_not_guess_ambiguous_vendor_curves() -> None:
    assert resolve_geology_channel("VENDOR_77", description="Geology value", unit="PCT") is None
    assert resolve_geology_channel("COLOR", description="Display color", unit="CODE") is None
    assert resolve_geology_channel("STRAT", description="Layer", unit="") is None
