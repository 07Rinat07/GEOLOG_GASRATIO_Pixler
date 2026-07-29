from __future__ import annotations

import ast
from dataclasses import dataclass
from fractions import Fraction
import math
import re
from typing import Callable


class EngineeringExpressionError(ValueError):
    """Raised when an engineering expression is invalid or unsafe."""


_ALLOWED_FUNCTIONS: dict[str, Callable[..., float]] = {
    "abs": abs,
    "acos": math.acos,
    "asin": math.asin,
    "atan": math.atan,
    "ceil": math.ceil,
    "cos": math.cos,
    "degrees": math.degrees,
    "exp": math.exp,
    "floor": math.floor,
    "ln": math.log,
    "log": math.log10,
    "log10": math.log10,
    "max": max,
    "min": min,
    "pow": pow,
    "radians": math.radians,
    "round": round,
    "sin": math.sin,
    "sqrt": math.sqrt,
    "tan": math.tan,
}
_ALLOWED_CONSTANTS = {"pi": math.pi, "e": math.e, "tau": math.tau}
_ALLOWED_BINOPS: dict[type[ast.operator], Callable[[float, float], float]] = {
    ast.Add: lambda left, right: left + right,
    ast.Sub: lambda left, right: left - right,
    ast.Mult: lambda left, right: left * right,
    ast.Div: lambda left, right: left / right,
    ast.FloorDiv: lambda left, right: left // right,
    ast.Mod: lambda left, right: left % right,
    ast.Pow: lambda left, right: left**right,
}
_ALLOWED_UNARYOPS: dict[type[ast.unaryop], Callable[[float], float]] = {
    ast.UAdd: lambda value: value,
    ast.USub: lambda value: -value,
}
_MIXED_FRACTION_RE = re.compile(
    r"(?<![\w.])(?P<whole>[+-]?\d+)\s+(?P<numerator>\d+)\s*/\s*(?P<denominator>\d+)(?![\w.])"
)
_HYPHEN_FRACTION_RE = re.compile(
    r"(?<![\w.])(?P<whole>[+-]?\d+)\s*-\s*(?P<numerator>\d+)\s*/\s*(?P<denominator>\d+)(?![\w.])"
)
_UNICODE_FRACTIONS = {
    "¼": Fraction(1, 4),
    "½": Fraction(1, 2),
    "¾": Fraction(3, 4),
    "⅐": Fraction(1, 7),
    "⅑": Fraction(1, 9),
    "⅒": Fraction(1, 10),
    "⅓": Fraction(1, 3),
    "⅔": Fraction(2, 3),
    "⅕": Fraction(1, 5),
    "⅖": Fraction(2, 5),
    "⅗": Fraction(3, 5),
    "⅘": Fraction(4, 5),
    "⅙": Fraction(1, 6),
    "⅚": Fraction(5, 6),
    "⅛": Fraction(1, 8),
    "⅜": Fraction(3, 8),
    "⅝": Fraction(5, 8),
    "⅞": Fraction(7, 8),
}


def _replace_mixed_fraction(match: re.Match[str]) -> str:
    whole = int(match.group("whole"))
    numerator = int(match.group("numerator"))
    denominator = int(match.group("denominator"))
    if denominator == 0:
        raise EngineeringExpressionError("Знаменатель дроби не может быть равен нулю")
    sign = -1 if whole < 0 else 1
    absolute = abs(whole) + numerator / denominator
    return f"({sign * absolute:.17g})"


def normalize_number_expression(value: str) -> str:
    normalized = value.strip().replace(",", ".").replace("×", "*").replace("÷", "/")
    for symbol, fraction in _UNICODE_FRACTIONS.items():
        pattern = re.compile(rf"(?<!\d)([+-]?\d+)?\s*{re.escape(symbol)}")

        def replace_unicode(match: re.Match[str], part: Fraction = fraction) -> str:
            whole_text = match.group(1)
            if not whole_text:
                return f"({float(part):.17g})"
            whole = int(whole_text)
            sign = -1 if whole < 0 else 1
            return f"({sign * (abs(whole) + float(part)):.17g})"

        normalized = pattern.sub(replace_unicode, normalized)
    normalized = _MIXED_FRACTION_RE.sub(_replace_mixed_fraction, normalized)
    normalized = _HYPHEN_FRACTION_RE.sub(_replace_mixed_fraction, normalized)
    return normalized


class EngineeringCalculator:
    """Small AST-based calculator that never executes arbitrary Python code."""

    def evaluate(self, expression: str) -> float:
        normalized = normalize_number_expression(expression)
        if not normalized:
            raise EngineeringExpressionError("Введите выражение")
        if len(normalized) > 500:
            raise EngineeringExpressionError("Выражение слишком длинное")
        try:
            root = ast.parse(normalized, mode="eval")
        except SyntaxError as exc:
            raise EngineeringExpressionError("Некорректное выражение") from exc
        value = self._evaluate_node(root.body, depth=0)
        if not math.isfinite(value):
            raise EngineeringExpressionError("Результат не является конечным числом")
        return value

    def _evaluate_node(self, node: ast.AST, *, depth: int) -> float:
        if depth > 30:
            raise EngineeringExpressionError("Выражение слишком сложное")
        if isinstance(node, ast.Constant) and isinstance(node.value, (int, float)):
            return float(node.value)
        if isinstance(node, ast.Name):
            try:
                return float(_ALLOWED_CONSTANTS[node.id])
            except KeyError as exc:
                raise EngineeringExpressionError(f"Неизвестная константа: {node.id}") from exc
        if isinstance(node, ast.BinOp):
            operation = _ALLOWED_BINOPS.get(type(node.op))
            if operation is None:
                raise EngineeringExpressionError("Операция не поддерживается")
            left = self._evaluate_node(node.left, depth=depth + 1)
            right = self._evaluate_node(node.right, depth=depth + 1)
            if isinstance(node.op, ast.Pow) and abs(right) > 1000:
                raise EngineeringExpressionError("Слишком большая степень")
            try:
                return float(operation(left, right))
            except (ArithmeticError, OverflowError, ValueError) as exc:
                raise EngineeringExpressionError(str(exc)) from exc
        if isinstance(node, ast.UnaryOp):
            operation = _ALLOWED_UNARYOPS.get(type(node.op))
            if operation is None:
                raise EngineeringExpressionError("Унарная операция не поддерживается")
            return float(operation(self._evaluate_node(node.operand, depth=depth + 1)))
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Name):
            function = _ALLOWED_FUNCTIONS.get(node.func.id)
            if function is None:
                raise EngineeringExpressionError(f"Функция не поддерживается: {node.func.id}")
            if node.keywords:
                raise EngineeringExpressionError("Именованные аргументы не поддерживаются")
            arguments = [self._evaluate_node(item, depth=depth + 1) for item in node.args]
            if len(arguments) > 16:
                raise EngineeringExpressionError("Слишком много аргументов")
            try:
                return float(function(*arguments))
            except (ArithmeticError, OverflowError, TypeError, ValueError) as exc:
                raise EngineeringExpressionError(str(exc)) from exc
        raise EngineeringExpressionError("В выражении присутствует запрещённая конструкция")


@dataclass(frozen=True, slots=True)
class UnitDefinition:
    key: str
    label: str
    to_base: Callable[[float], float]
    from_base: Callable[[float], float]


def _linear(key: str, label: str, factor: float) -> UnitDefinition:
    return UnitDefinition(
        key,
        label,
        lambda value, scale=factor: value * scale,
        lambda value, scale=factor: value / scale,
    )


_UNIT_CATEGORIES: dict[str, tuple[str, tuple[UnitDefinition, ...]]] = {
    "length": (
        "Длина",
        (
            _linear("mm", "мм", 0.001),
            _linear("cm", "см", 0.01),
            _linear("m", "м", 1.0),
            _linear("km", "км", 1000.0),
            _linear("in", "дюйм (in)", 0.0254),
            _linear("ft", "фут (ft)", 0.3048),
            _linear("yd", "ярд (yd)", 0.9144),
        ),
    ),
    "pressure": (
        "Давление",
        (
            _linear("pa", "Па", 1.0),
            _linear("kpa", "кПа", 1_000.0),
            _linear("mpa", "МПа", 1_000_000.0),
            _linear("bar", "бар", 100_000.0),
            _linear("atm", "атм", 101_325.0),
            _linear("psi", "psi", 6_894.757293168),
            _linear("mmhg", "мм рт. ст.", 133.322387415),
            _linear("kgf_cm2", "кгс/см²", 98_066.5),
        ),
    ),
    "temperature": (
        "Температура",
        (
            UnitDefinition("c", "°C", lambda value: value + 273.15, lambda value: value - 273.15),
            UnitDefinition(
                "f",
                "°F",
                lambda value: (value - 32.0) * 5.0 / 9.0 + 273.15,
                lambda value: (value - 273.15) * 9.0 / 5.0 + 32.0,
            ),
            UnitDefinition("k", "K", lambda value: value, lambda value: value),
        ),
    ),
    "area": (
        "Площадь",
        (
            _linear("mm2", "мм²", 1e-6),
            _linear("cm2", "см²", 1e-4),
            _linear("m2", "м²", 1.0),
            _linear("ha", "га", 10_000.0),
            _linear("in2", "дюйм²", 0.00064516),
            _linear("ft2", "фут²", 0.09290304),
        ),
    ),
    "volume": (
        "Объём",
        (
            _linear("ml", "мл", 1e-6),
            _linear("l", "л", 0.001),
            _linear("m3", "м³", 1.0),
            _linear("cm3", "см³", 1e-6),
            _linear("in3", "дюйм³", 1.6387064e-5),
            _linear("ft3", "фут³", 0.028316846592),
            _linear("bbl", "баррель (bbl)", 0.158987294928),
        ),
    ),
    "mass": (
        "Масса",
        (
            _linear("mg", "мг", 1e-6),
            _linear("g", "г", 0.001),
            _linear("kg", "кг", 1.0),
            _linear("t", "т", 1000.0),
            _linear("lb", "фунт (lb)", 0.45359237),
        ),
    ),
    "force": (
        "Сила",
        (
            _linear("n", "Н", 1.0),
            _linear("kn", "кН", 1000.0),
            _linear("kgf", "кгс", 9.80665),
            _linear("lbf", "фунт-сила (lbf)", 4.4482216152605),
        ),
    ),
    "torque": (
        "Крутящий момент",
        (
            _linear("nm", "Н·м", 1.0),
            _linear("knm", "кН·м", 1000.0),
            _linear("kgfm", "кгс·м", 9.80665),
            _linear("lbfft", "lbf·ft", 1.3558179483314),
        ),
    ),
    "density": (
        "Плотность",
        (
            _linear("kg_m3", "кг/м³", 1.0),
            _linear("g_cm3", "г/см³", 1000.0),
            _linear("lb_ft3", "lb/ft³", 16.01846337396),
            _linear("ppg", "lb/US gal (ppg)", 119.826427316),
        ),
    ),
    "flow": (
        "Расход",
        (
            _linear("m3_s", "м³/с", 1.0),
            _linear("m3_h", "м³/ч", 1.0 / 3600.0),
            _linear("l_s", "л/с", 0.001),
            _linear("l_min", "л/мин", 0.001 / 60.0),
            _linear("bbl_d", "bbl/сут", 0.158987294928 / 86400.0),
            _linear("gpm", "US gal/min", 0.003785411784 / 60.0),
        ),
    ),
    "speed": (
        "Скорость",
        (
            _linear("m_s", "м/с", 1.0),
            _linear("km_h", "км/ч", 1.0 / 3.6),
            _linear("ft_s", "ft/s", 0.3048),
            _linear("mph", "mph", 0.44704),
        ),
    ),
    "energy": (
        "Энергия",
        (
            _linear("j", "Дж", 1.0),
            _linear("kj", "кДж", 1000.0),
            _linear("mj", "МДж", 1_000_000.0),
            _linear("kwh", "кВт·ч", 3_600_000.0),
            _linear("btu", "BTU", 1055.05585262),
        ),
    ),
    "angle": (
        "Угол",
        (
            _linear("rad", "радиан", 1.0),
            _linear("deg", "градус", math.pi / 180.0),
        ),
    ),
}


class UnitConverter:
    def __init__(self) -> None:
        self._categories = _UNIT_CATEGORIES

    def categories(self) -> tuple[tuple[str, str], ...]:
        return tuple((key, item[0]) for key, item in self._categories.items())

    def units(self, category: str) -> tuple[tuple[str, str], ...]:
        try:
            definitions = self._categories[category][1]
        except KeyError as exc:
            raise KeyError(f"Неизвестная категория единиц: {category}") from exc
        return tuple((item.key, item.label) for item in definitions)

    def parse_value(self, value: str) -> float:
        return EngineeringCalculator().evaluate(value)

    def convert(self, value: str | float, category: str, source: str, target: str) -> float:
        numeric = self.parse_value(value) if isinstance(value, str) else float(value)
        definitions = {item.key: item for item in self._categories[category][1]}
        try:
            source_definition = definitions[source]
            target_definition = definitions[target]
        except KeyError as exc:
            raise KeyError("Единица не относится к выбранной категории") from exc
        base_value = source_definition.to_base(numeric)
        result = target_definition.from_base(base_value)
        if not math.isfinite(result):
            raise ValueError("Результат преобразования не является конечным числом")
        return result


def format_engineering_value(value: float) -> str:
    absolute = abs(value)
    if absolute != 0.0 and (absolute >= 1e9 or absolute < 1e-6):
        return f"{value:.12e}".rstrip("0").rstrip(".")
    return f"{value:.12f}".rstrip("0").rstrip(".")
