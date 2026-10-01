from geoworkbench.printing.hydrocarbon_fluid_markers import (
    all_fluid_marker_specs,
    fluid_marker_legend_specs,
    fluid_marker_spec,
    marker_lane_offsets,
    marker_lanes,
)
from geoworkbench.services.fluid_phase_contract import fluid_hypothesis_phase_label
from geoworkbench.services.localization import AppLanguage
from geoworkbench.services.opus_report_labels import opus_report_label


def test_fluid_marker_palette_has_unique_category_codes_and_colors() -> None:
    specs = all_fluid_marker_specs()

    assert len({item.category for item in specs}) == len(specs)
    assert len({item.code for item in specs}) == len(specs)
    assert len({item.color for item in specs}) == len(specs)
    assert len({item.shape for item in specs}) == len(specs)


def test_standard_and_opus_hypotheses_share_physical_fluid_families() -> None:
    pairs = (
        ("probable_gas", "opus_gasomer_combustible_gas", "G"),
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


def test_marker_and_headline_share_the_same_phase_contract() -> None:
    for hypothesis in (
        "probable_gas",
        "wet_gas_or_gas_condensate",
        "light_oil_high_gor",
        "productive_oil_decreasing_gravity",
        "probable_liquid_hydrocarbons",
        "gas_condensate_or_high_api_oil",
        "opus_gasomer_combustible_gas",
        "opus_gasomer_gas_condensate",
        "opus_gasomer_oil",
        "opus_gasomer_water_dissolved_gas",
        "opus_gasomer_undefined",
    ):
        assert (
            fluid_marker_spec(hypothesis).label(AppLanguage.RU)
            == fluid_hypothesis_phase_label(hypothesis, AppLanguage.RU)
        )

    assert fluid_marker_spec("wet_gas_or_gas_condensate").code == "G"
    assert fluid_marker_spec("opus_gasomer_gas_condensate").code == "GC"


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

    assert (
        spec.label(AppLanguage.RU)
        == "жидкая УВ-фаза; возможны лёгкая нефть или газоконденсат"
    )
    assert (
        spec.label(AppLanguage.KK)
        == "сұйық КС фазасы; жеңіл мұнай немесе газ конденсаты болуы мүмкін"
    )
    assert (
        spec.label(AppLanguage.EN)
        == "liquid hydrocarbon phase; light oil or gas condensate possible"
    )


def test_marker_labels_use_only_the_bounded_phase_contract() -> None:
    allowed = {
        "УВ-флюид неопределённого типа",
        "жидкая УВ-фаза",
        "признаки лёгкой нефтяной фазы",
        "жидкая УВ-фаза; возможны лёгкая нефть или газоконденсат",
        "газовая УВ-фаза",
    }

    assert {
        spec.label(AppLanguage.RU)
        for spec in all_fluid_marker_specs()
    } <= allowed


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



def test_opus_class_labels_use_phase_wording_in_three_languages() -> None:
    assert opus_report_label("class_2", AppLanguage.RU) == "Признаки нефтяной фазы"
    assert opus_report_label("class_2", AppLanguage.KK) == "Мұнай фазасының белгілері"
    assert opus_report_label("class_2", AppLanguage.EN) == "Indications of an oil phase"

    assert (
        opus_report_label("class_6", AppLanguage.RU)
        == "Признаки газированной нефтяной фазы"
    )
    assert (
        opus_report_label("class_7", AppLanguage.RU)
        == "УВ-флюид неопределённого типа"
    )


def test_opus_graph_markers_do_not_use_old_oil_wording() -> None:
    labels = tuple(
        fluid_marker_spec(hypothesis).label(AppLanguage.RU)
        for hypothesis in (
            "opus_gasomer_oil",
            "opus_gasomer_gassy_oil",
            "opus_gasomer_oxidized_residual_oil",
            "opus_gasomer_undefined",
        )
    )

    assert labels == (
        "жидкая УВ-фаза",
        "жидкая УВ-фаза",
        "жидкая УВ-фаза",
        "УВ-флюид неопределённого типа",
    )
    assert all("нефт" not in label.casefold() for label in labels)
