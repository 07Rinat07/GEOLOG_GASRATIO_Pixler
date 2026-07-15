import numpy as np
import pytest

from geoworkbench.calculations.pixler import (
    FormulaCategory,
    FormulaControlExample,
    FormulaProfile,
    FormulaProfileRegistry,
    build_all_sourced_formula_registry,
    build_sourced_formula_registry,
)


def make_profile(*, expected: tuple[float, ...] = (2.0, 3.0)) -> FormulaProfile:
    return FormulaProfile(
        profile_id="verified.sum",
        display_name="Verified sum",
        version="1.0.0",
        category=FormulaCategory.OTHER,
        source="Internal arithmetic specification, section 1",
        expression="SUM = A + B",
        required_inputs=("A", "B"),
        input_units={"A": "%", "B": "%"},
        output_mnemonic="SUM",
        output_unit="%",
        description="Sum of two inputs",
        formula=lambda inputs, parameters: inputs["A"] + inputs["B"],
        control_example=FormulaControlExample(
            inputs={"A": (1.0, 1.0), "B": (1.0, 2.0)},
            expected=expected,
        ),
    )


def test_registry_validates_example_and_exposes_passport() -> None:
    registry = FormulaProfileRegistry()
    registry.register(make_profile())

    passport = registry.passport("verified.sum")

    assert passport.expression == "SUM = A + B"
    assert passport.output_mnemonic == "SUM"
    assert passport.input_units == {"A": "%", "B": "%"}
    np.testing.assert_allclose(
        registry.calculate(
            "verified.sum",
            {"a": np.array([2.0]), "b": np.array([3.0])},
        ),
        [5.0],
    )


def test_registry_rejects_failed_control_example_without_registration() -> None:
    registry = FormulaProfileRegistry()

    with pytest.raises(ValueError, match="Контрольный пример"):
        registry.register(make_profile(expected=(99.0, 99.0)))

    assert registry.available() == ()


def test_registry_builds_dependency_graph_from_profiles() -> None:
    registry = FormulaProfileRegistry()
    registry.register(make_profile())

    graph = registry.build_dependency_graph()

    assert graph.affected_outputs({"A"}) == ["SUM"]
    assert graph.affected_outputs({"B"}) == ["SUM"]


def test_registry_rejects_mismatched_input_shapes_and_result_shape() -> None:
    registry = FormulaProfileRegistry()
    registry.register(make_profile())

    with pytest.raises(ValueError, match="одинаковую форму"):
        registry.calculate(
            "verified.sum",
            {"A": np.array([1.0]), "B": np.array([1.0, 2.0])},
        )

    bad_result = make_profile()
    bad_result = FormulaProfile(
        **{
            field: getattr(bad_result, field)
            for field in bad_result.__dataclass_fields__
            if field != "formula"
        },
        formula=lambda inputs, parameters: np.array([1.0]),
    )
    with pytest.raises(ValueError, match="форме"):
        FormulaProfileRegistry().register(bad_result)


@pytest.mark.parametrize(
    "changes",
    [
        {"profile_id": "Invalid ID"},
        {"expression": ""},
        {"required_inputs": ()},
        {"required_inputs": ("A", "a")},
        {"input_units": {"A": "%"}},
    ],
)
def test_registry_rejects_incomplete_passport(changes: dict[str, object]) -> None:
    source = make_profile()
    values = {field: getattr(source, field) for field in source.__dataclass_fields__}
    values.update(changes)

    with pytest.raises(ValueError):
        FormulaProfileRegistry().register(FormulaProfile(**values))


def test_sourced_haworth_and_pixler_profiles() -> None:
    registry = build_sourced_formula_registry()
    inputs = {
        "C1": np.array([80.0]),
        "C2": np.array([10.0]),
        "C3": np.array([5.0]),
        "IC4": np.array([1.0]),
        "NC4": np.array([2.0]),
        "IC5": np.array([1.0]),
        "NC5": np.array([1.0]),
    }

    assert len(registry.available()) == 7
    np.testing.assert_allclose(registry.calculate("haworth.wetness", inputs), [20.0])
    np.testing.assert_allclose(registry.calculate("haworth.balance", inputs), [9.0])
    np.testing.assert_allclose(registry.calculate("haworth.character", inputs), [1.0])
    np.testing.assert_allclose(registry.calculate("pixler.c1_c4", inputs), [80.0 / 3.0])
    assert "10.2118/2254-PA" in registry.passport("pixler.c1_c2").source


def test_sourced_profiles_return_nan_for_zero_denominator() -> None:
    registry = build_sourced_formula_registry()
    result = registry.calculate(
        "pixler.c1_c2",
        {"C1": np.array([1.0]), "C2": np.array([0.0])},
    )
    assert np.isnan(result[0])


def test_sourced_d_exponent_profiles() -> None:
    registry = build_all_sourced_formula_registry()
    d_value = registry.calculate(
        "dexp.jorden_shirley",
        {
            "ROP_FPH": np.array([60.0]),
            "RPM": np.array([100.0]),
            "WOB_LBF": np.array([50_000.0]),
            "BIT_IN": np.array([10.0]),
        },
    )
    corrected = registry.calculate(
        "dexp.rehm_mcclendon_corrected",
        {
            "DEXP": d_value,
            "RHO_N_PPG": np.array([9.0]),
            "RHO_A_PPG": np.array([12.0]),
        },
    )

    np.testing.assert_allclose(d_value, [1.6368638103758524])
    np.testing.assert_allclose(corrected, d_value * 0.75)
    graph = registry.build_dependency_graph()
    affected = graph.affected_outputs({"ROP_FPH"})
    assert set(affected) == {"C1_NORM", "DEXP", "DEXPC"}
    assert affected.index("DEXP") < affected.index("DEXPC")


def test_sourced_normalized_gas_profile() -> None:
    registry = build_all_sourced_formula_registry()
    result = registry.calculate(
        "gas.normalized_c1_us20140379265",
        {
            "C1": np.array([10.0, 20.0, 10.0]),
            "FLOW_GPM": np.array([500.0, 500.0, 500.0]),
            "ROP_FPH": np.array([50.0, 100.0, 0.0]),
            "BIT_IN": np.array([10.0, 10.0, 10.0]),
        },
    )

    np.testing.assert_allclose(result[:2], [11.6, 11.6])
    assert np.isnan(result[2])
    passport = registry.passport("gas.normalized_c1_us20140379265")
    assert "US20140379265A1" in passport.source
    assert passport.output_mnemonic == "C1_NORM"


@pytest.mark.parametrize(
    "values",
    [
        (0.0, 100.0, 50_000.0, 10.0),
        (60.0, 0.0, 50_000.0, 10.0),
        (60.0, 100.0, 0.0, 10.0),
        (60.0, 100.0, 50_000.0, 0.0),
    ],
)
def test_d_exponent_invalid_log_domain_returns_nan(values: tuple[float, ...]) -> None:
    registry = build_all_sourced_formula_registry()
    result = registry.calculate(
        "dexp.jorden_shirley",
        {
            name: np.array([value])
            for name, value in zip(("ROP_FPH", "RPM", "WOB_LBF", "BIT_IN"), values, strict=True)
        },
    )
    assert np.isnan(result[0])
