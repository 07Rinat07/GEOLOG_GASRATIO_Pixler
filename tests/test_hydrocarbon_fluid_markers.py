from geoworkbench.printing.hydrocarbon_fluid_markers import (
    all_fluid_marker_specs,
    fluid_marker_legend_specs,
    fluid_marker_spec,
    marker_lane_offsets,
    marker_lanes,
)
from geoworkbench.services.localization import AppLanguage


def test_fluid_marker_palette_has_unique_category_codes_and_colors() -> None:
    specs = all_fluid_marker_specs()

    assert len({item.category for item in specs}) == len(specs)
    assert len({item.code for item in specs}) == len(specs)
    assert len({item.color for item in specs}) == len(specs)
    assert len({item.shape for item in specs}) == len(specs)


def test_standard_and_opus_hypotheses_share_physical_fluid_families() -> None:
    pairs = (
        ("probable_gas", "opus_gasomer_combustible_gas", "G"),
        ("wet_gas_or_gas_condensate", "opus_gasomer_gas_condensate", "GC"),
        ("productive_oil_decreasing_gravity", "opus_gasomer_oil", "O"),
        ("heavy_or_residual_oil", "opus_gasomer_oxidized_residual_oil", "HO"),
        ("opus_gassy_oil", "opus_gasomer_gassy_oil", "GO"),
        ("opus_water_dissolved_gas", "opus_gasomer_water_dissolved_gas", "DG"),
    )

    for standard, opus, code in pairs:
        left = fluid_marker_spec(standard)
        right = fluid_marker_spec(opus)
        assert left.category == right.category
        assert left.code == right.code == code
        assert left.color == right.color
        assert left.shape == right.shape


def test_opus_ambiguous_and_no_consensus_stay_indeterminate() -> None:
    for hypothesis in (
        "opus_no_consensus",
        "opus_gasomer_undefined",
        "opus_gasomer_no_consensus",
        "opus_gasomer_ambiguous__possible__2-3",
    ):
        spec = fluid_marker_spec(hypothesis)
        assert spec.category == "indeterminate"
        assert spec.code == "?"


def test_opus_fallback_uses_same_marker_as_underlying_hypothesis() -> None:
    fallback = fluid_marker_spec("opus_fallback__light_oil_high_gor")
    direct = fluid_marker_spec("light_oil_high_gor")

    assert fallback == direct


def test_marker_legend_deduplicates_categories_and_keeps_canonical_order() -> None:
    specs = fluid_marker_legend_specs(
        [
            "opus_gasomer_oil",
            "productive_oil_decreasing_gravity",
            "probable_gas",
            "opus_gasomer_combustible_gas",
        ]
    )

    assert [item.code for item in specs] == ["G", "O"]


def test_marker_labels_are_available_for_ru_kk_en() -> None:
    spec = fluid_marker_spec("opus_gasomer_gas_condensate")

    assert spec.label(AppLanguage.RU) == "газ-конденсат"
    assert spec.label(AppLanguage.KK) == "газ-конденсат"
    assert spec.label(AppLanguage.EN) == "gas condensate"


def test_dense_markers_use_horizontal_lanes_without_changing_y_positions() -> None:
    y_positions = (100.0, 101.0, 102.0, 130.0)
    lanes = marker_lanes(y_positions, minimum_gap=8.0)

    assert len(lanes) == len(y_positions)
    assert len(set(lanes[:3])) == 3
    assert lanes[3] == 0
    assert y_positions == (100.0, 101.0, 102.0, 130.0)


def test_dense_lane_offsets_stay_inside_reserved_zone() -> None:
    offsets = marker_lane_offsets(64, zone_width=120.0, max_spacing=12.0)

    assert len(offsets) == 64
    assert offsets == tuple(sorted(offsets))
    assert offsets[0] > 0.0
    assert offsets[-1] < 120.0
    assert len(set(offsets)) == 64
