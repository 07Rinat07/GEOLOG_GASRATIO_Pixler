from __future__ import annotations

from dataclasses import dataclass
from typing import Callable

import numpy as np
from numpy.typing import NDArray


Array = NDArray[np.float64]
Formula = Callable[[dict[str, Array], dict[str, float]], Array]


@dataclass(frozen=True, slots=True)
class FormulaProfile:
    profile_id: str
    display_name: str
    version: str
    source: str
    required_inputs: tuple[str, ...]
    formula: Formula


class FormulaProfileRegistry:
    """Реестр подтверждённых методик.

    Реестр изначально пуст: формулы Pixler и коэффициентов флюидности должны
    добавляться только вместе с рабочей методикой/источником и тестовым примером.
    """

    def __init__(self) -> None:
        self._profiles: dict[str, FormulaProfile] = {}

    def register(self, profile: FormulaProfile) -> None:
        if not profile.source.strip():
            raise ValueError("Для формулы обязателен источник")
        if profile.profile_id in self._profiles:
            raise ValueError(f"Профиль уже зарегистрирован: {profile.profile_id}")
        self._profiles[profile.profile_id] = profile

    def available(self) -> tuple[FormulaProfile, ...]:
        return tuple(self._profiles.values())

    def calculate(
        self,
        profile_id: str,
        inputs: dict[str, Array],
        parameters: dict[str, float] | None = None,
    ) -> Array:
        try:
            profile = self._profiles[profile_id]
        except KeyError as exc:
            raise KeyError(f"Неизвестный профиль формулы: {profile_id}") from exc

        normalized = {name.upper(): np.asarray(value, dtype=np.float64) for name, value in inputs.items()}
        missing = [name for name in profile.required_inputs if name.upper() not in normalized]
        if missing:
            raise KeyError(f"Для профиля отсутствуют входы: {', '.join(missing)}")
        return np.asarray(profile.formula(normalized, parameters or {}), dtype=np.float64)
