from __future__ import annotations

import re
from dataclasses import dataclass
from enum import StrEnum
from typing import Callable, Mapping

import numpy as np
from numpy.typing import NDArray

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
        missing_units = [name for name in normalized_inputs if not profile.input_units.get(name, "").strip()]
        if missing_units:
            raise ValueError(f"Не заданы единицы входов: {', '.join(missing_units)}")
        example_inputs = {name.upper() for name in profile.control_example.inputs}
        missing_example_inputs = set(normalized_inputs) - example_inputs
        if missing_example_inputs:
            missing = ", ".join(sorted(missing_example_inputs))
            raise ValueError(f"В контрольном примере отсутствуют входы: {missing}")
