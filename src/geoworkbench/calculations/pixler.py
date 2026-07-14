from __future__ import annotations

import re
from dataclasses import dataclass
from enum import StrEnum
from typing import Callable, Mapping

import numpy as np
from numpy.typing import NDArray

from geoworkbench.calculations.gas_ratio import safe_ratio
from geoworkbench.services.dependency_graph import DependencyGraph


Array = NDArray[np.float64]
Formula = Callable[[dict[str, Array], dict[str, float]], Array]
_PROFILE_ID_PATTERN = re.compile(r"^[a-z][a-z0-9]*(?:[._-][a-z0-9]+)*$")


class FormulaCategory(StrEnum):
    GAS_RATIO = "gas_ratio"
    PIXLER = "pixler"
    FLUID = "fluid"
    DEXP = "dexp"
    OTHER = "other"


@dataclass(frozen=True, slots=True)
class FormulaControlExample:
    inputs: Mapping[str, tuple[float, ...]]
    expected: tuple[float, ...]
    parameters: Mapping[str, float] | None = None


@dataclass(frozen=True, slots=True)
class FormulaProfile:
    profile_id: str
    display_name: str
    version: str
    category: FormulaCategory
    source: str
    expression: str
    required_inputs: tuple[str, ...]
    input_units: Mapping[str, str]
    output_mnemonic: str
    output_unit: str
    description: str
    formula: Formula
    control_example: FormulaControlExample


@dataclass(frozen=True, slots=True)
class FormulaPassport:
    profile_id: str
    display_name: str
    version: str
    category: FormulaCategory
    source: str
    expression: str
    required_inputs: tuple[str, ...]
    input_units: Mapping[str, str]
    output_mnemonic: str
    output_unit: str
    description: str


class FormulaProfileRegistry:
    """Registry of sourced, versioned and numerically verified formula profiles."""

    def __init__(self) -> None:
        self._profiles: dict[str, FormulaProfile] = {}

    def register(self, profile: FormulaProfile) -> None:
        self._validate_profile(profile)
        if profile.profile_id in self._profiles:
            raise ValueError(f"Профиль уже зарегистрирован: {profile.profile_id}")
        self._profiles[profile.profile_id] = profile
        try:
            self.validate_control_example(profile.profile_id)
        except Exception:
            del self._profiles[profile.profile_id]
            raise

    def available(self) -> tuple[FormulaProfile, ...]:
        return tuple(self._profiles.values())

    def passport(self, profile_id: str) -> FormulaPassport:
        profile = self._require_profile(profile_id)
        return FormulaPassport(
            profile_id=profile.profile_id,
            display_name=profile.display_name,
            version=profile.version,
            category=profile.category,
            source=profile.source,
            expression=profile.expression,
            required_inputs=profile.required_inputs,
            input_units=dict(profile.input_units),
            output_mnemonic=profile.output_mnemonic,
            output_unit=profile.output_unit,
            description=profile.description,
        )

    def calculate(
        self,
        profile_id: str,
        inputs: Mapping[str, Array],
        parameters: Mapping[str, float] | None = None,
    ) -> Array:
        profile = self._require_profile(profile_id)
        normalized = {
            name.upper(): np.asarray(value, dtype=np.float64) for name, value in inputs.items()
        }
        required_names = tuple(name.upper() for name in profile.required_inputs)
        missing = [name for name in required_names if name not in normalized]
        if missing:
            raise KeyError(f"Для профиля отсутствуют входы: {', '.join(missing)}")
        shapes = {normalized[name].shape for name in required_names}
        if len(shapes) != 1:
            raise ValueError("Входы формулы должны иметь одинаковую форму")
        result = np.asarray(
            profile.formula(normalized, dict(parameters or {})),
            dtype=np.float64,
        )
        expected_shape = normalized[required_names[0]].shape
        if result.shape != expected_shape:
            raise ValueError("Результат формулы должен совпадать по форме с входами")
        return result

    def validate_control_example(
        self,
        profile_id: str,
        *,
        rtol: float = 1e-9,
        atol: float = 1e-12,
    ) -> None:
        profile = self._require_profile(profile_id)
        example = profile.control_example
        inputs = {
            name: np.asarray(values, dtype=np.float64) for name, values in example.inputs.items()
        }
        actual = self.calculate(profile_id, inputs, example.parameters)
        expected = np.asarray(example.expected, dtype=np.float64)
        if actual.shape != expected.shape or not np.allclose(
            actual,
            expected,
            rtol=rtol,
            atol=atol,
            equal_nan=True,
        ):
            raise ValueError(f"Контрольный пример профиля не пройден: {profile_id}")

    def build_dependency_graph(self) -> DependencyGraph:
        graph = DependencyGraph()
        for profile in self._profiles.values():
            for input_mnemonic in profile.required_inputs:
                graph.add_dependency(input_mnemonic.upper(), profile.output_mnemonic.upper())
        return graph

    def _require_profile(self, profile_id: str) -> FormulaProfile:
        try:
            return self._profiles[profile_id]
        except KeyError as exc:
            raise KeyError(f"Неизвестный профиль формулы: {profile_id}") from exc

    @staticmethod
    def _validate_profile(profile: FormulaProfile) -> None:
        if not _PROFILE_ID_PATTERN.fullmatch(profile.profile_id):
            raise ValueError(f"Некорректный ID профиля: {profile.profile_id!r}")
        required_text = {
            "название": profile.display_name,
            "версия": profile.version,
            "источник": profile.source,
            "выражение": profile.expression,
            "выходная мнемоника": profile.output_mnemonic,
            "единица результата": profile.output_unit,
            "описание": profile.description,
        }
        for field_name, value in required_text.items():
            if not value.strip():
                raise ValueError(f"Поле '{field_name}' не может быть пустым")
        normalized_inputs = tuple(name.upper() for name in profile.required_inputs)
        if not normalized_inputs or len(set(normalized_inputs)) != len(normalized_inputs):
            raise ValueError("Входы формулы должны быть непустыми и уникальными")
        missing_units = [
            name for name in normalized_inputs if not profile.input_units.get(name, "").strip()
        ]
        if missing_units:
            raise ValueError(f"Не заданы единицы входов: {', '.join(missing_units)}")
        example_inputs = {name.upper() for name in profile.control_example.inputs}
        missing_example_inputs = set(normalized_inputs) - example_inputs
        if missing_example_inputs:
            missing = ", ".join(sorted(missing_example_inputs))
            raise ValueError(f"В контрольном примере отсутствуют входы: {missing}")


HAWORTH_SOURCE = (
    "Haworth, J.H., Sellens, M., Whittaker, A. (1985). Interpretation of Hydrocarbon "
    "Shows Using Light C1-C5 Hydrocarbon Gases from Mud-Log Data. AAPG Bulletin "
    "69(8), 1305-1310."
)
PIXLER_SOURCE = (
    "Pixler, B.O. (1969). Formation Evaluation by Analysis of Hydrocarbon Ratios. "
    "Journal of Petroleum Technology 21(6), 665-670. DOI: 10.2118/2254-PA."
)
_GAS_UNITS = {
    name: "same concentration unit" for name in ("C1", "C2", "C3", "IC4", "NC4", "IC5", "NC5")
}


def sourced_gas_ratio_profiles() -> tuple[FormulaProfile, ...]:
    """Return public Haworth and Pixler profiles with registration-time examples."""

    example_inputs = {
        "C1": (80.0,),
        "C2": (10.0,),
        "C3": (5.0,),
        "IC4": (1.0,),
        "NC4": (2.0,),
        "IC5": (1.0,),
        "NC5": (1.0,),
    }
    all_inputs = tuple(example_inputs)

    def heavy(inputs: dict[str, Array]) -> Array:
        return inputs["C3"] + inputs["IC4"] + inputs["NC4"] + inputs["IC5"] + inputs["NC5"]

    def profile(
        profile_id: str,
        display_name: str,
        category: FormulaCategory,
        source: str,
        expression: str,
        required_inputs: tuple[str, ...],
        output_mnemonic: str,
        description: str,
        formula: Formula,
        expected: float,
    ) -> FormulaProfile:
        return FormulaProfile(
            profile_id=profile_id,
            display_name=display_name,
            version="1.0.0",
            category=category,
            source=source,
            expression=expression,
            required_inputs=required_inputs,
            input_units={name: _GAS_UNITS[name] for name in required_inputs},
            output_mnemonic=output_mnemonic,
            output_unit="ratio" if output_mnemonic != "WH" else "%",
            description=description,
            formula=formula,
            control_example=FormulaControlExample(
                inputs={name: example_inputs[name] for name in required_inputs},
                expected=(expected,),
            ),
        )

    def pixler_ratio(denominator_names: tuple[str, ...]) -> Formula:
        def calculate(inputs: dict[str, Array], parameters: dict[str, float]) -> Array:
            denominator = sum(
                (inputs[name] for name in denominator_names),
                start=np.zeros_like(inputs["C1"]),
            )
            return safe_ratio(inputs["C1"], denominator)

        return calculate

    profiles = [
        profile(
            "haworth.wetness",
            "Haworth Wetness",
            FormulaCategory.FLUID,
            HAWORTH_SOURCE,
            "Wh = 100 * (C2 + C3 + iC4 + nC4 + iC5 + nC5) / (C1 + C2 + C3 + iC4 + nC4 + iC5 + nC5)",
            all_inputs,
            "WH",
            "Доля компонентов C2-C5 в сумме C1-C5.",
            lambda i, p: 100.0 * safe_ratio(i["C2"] + heavy(i), i["C1"] + i["C2"] + heavy(i)),
            20.0,
        ),
        profile(
            "haworth.balance",
            "Haworth Balance",
            FormulaCategory.FLUID,
            HAWORTH_SOURCE,
            "Bh = (C1 + C2) / (C3 + iC4 + nC4 + iC5 + nC5)",
            all_inputs,
            "BH",
            "Баланс лёгких и тяжёлых компонентов.",
            lambda i, p: safe_ratio(i["C1"] + i["C2"], heavy(i)),
            9.0,
        ),
        profile(
            "haworth.character",
            "Haworth Character",
            FormulaCategory.FLUID,
            HAWORTH_SOURCE,
            "Ch = (iC4 + nC4 + iC5 + nC5) / C3",
            ("C3", "IC4", "NC4", "IC5", "NC5"),
            "CH",
            "Отношение суммы C4-C5 к пропану.",
            lambda i, p: safe_ratio(i["IC4"] + i["NC4"] + i["IC5"] + i["NC5"], i["C3"]),
            1.0,
        ),
    ]
    for denominator, output, expected in (
        (("C2",), "C1_C2", 8.0),
        (("C3",), "C1_C3", 16.0),
        (("IC4", "NC4"), "C1_C4", 80.0 / 3.0),
        (("IC5", "NC5"), "C1_C5", 40.0),
    ):
        required = ("C1", *denominator)
        denominator_text = " + ".join(denominator)
        profiles.append(
            profile(
                f"pixler.{output.lower()}",
                f"Pixler {output.replace('_', '/')}",
                FormulaCategory.PIXLER,
                PIXLER_SOURCE,
                f"{output} = C1 / ({denominator_text})",
                required,
                output,
                "Отношение метана к более тяжёлому компоненту Pixler.",
                pixler_ratio(denominator),
                expected,
            )
        )
    return tuple(profiles)


def build_sourced_formula_registry() -> FormulaProfileRegistry:
    registry = FormulaProfileRegistry()
    for profile in sourced_gas_ratio_profiles():
        registry.register(profile)
    return registry
