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
    assert resolve_geology_channel(
        "VENDOR_1", description="Laboratory calcite CaCO3 content", unit="",
    ) is None
    assert resolve_geology_channel("CARBONATE_PCT").role is GeologyChannelRole.LEGACY_CARBONATE


def test_resolver_accepts_common_calcimetry_formula_spellings() -> None:
    cases = {
        "CA_CO3": GeologyChannelRole.CALCITE,
        "КАЛЬЦИТ_CACO3": GeologyChannelRole.CALCITE,
        "CA_MG_CO3_2": GeologyChannelRole.DOLOMITE,
        "CAMGCO32": GeologyChannelRole.DOLOMITE,
        "ОБЩАЯ_КАРБОНАТНОСТЬ": GeologyChannelRole.LEGACY_CARBONATE,
    }
    for mnemonic, role in cases.items():
        match = resolve_geology_channel(mnemonic)
        assert match is not None
        assert match.role is role


def test_resolver_recognizes_opaque_vendor_cuttings_channels_from_descriptions() -> None:
    primary = resolve_geology_channel(
        "S701",
        description="Код основной породы",
        unit="CODE",
    )
    rock_1 = resolve_geology_channel(
        "S711",
        description="Код породы 1",
        unit="CODE",
    )
    amount_1 = resolve_geology_channel(
        "S712",
        description="Содержание породы 1",
        unit="%",
    )
    rock_3 = resolve_geology_channel(
        "CH33",
        description="Rock 3 code",
        unit="ID",
    )
    amount_3 = resolve_geology_channel(
        "CH34",
        description="Rock 3 percentage",
        unit="PCT",
    )

    assert primary is not None
    assert primary.role is GeologyChannelRole.PRIMARY_LITHOLOGY
    assert primary.matched_by == "description+uom"

    assert rock_1 is not None
    assert rock_1.role is GeologyChannelRole.CUTTINGS_CODE
    assert rock_1.slot == 1
    assert amount_1 is not None
    assert amount_1.role is GeologyChannelRole.CUTTINGS_AMOUNT
    assert amount_1.slot == 1

    assert rock_3 is not None
    assert rock_3.role is GeologyChannelRole.CUTTINGS_CODE
    assert rock_3.slot == 3
    assert amount_3 is not None
    assert amount_3.role is GeologyChannelRole.CUTTINGS_AMOUNT
    assert amount_3.slot == 3


def test_description_based_cuttings_mapping_requires_compatible_units() -> None:
    assert resolve_geology_channel(
        "S711",
        description="Код породы 1",
        unit="%",
    ) is None
    assert resolve_geology_channel(
        "S712",
        description="Содержание породы 1",
        unit="CODE",
    ) is None
    assert resolve_geology_channel(
        "S701",
        description="Основная порода",
        unit="%",
    ) is None
