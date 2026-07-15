from __future__ import annotations

import ast
import operator
import re
from collections.abc import Mapping
from typing import Any, Callable, cast

import numpy as np

from geoworkbench.calculations.pixler import Array
from geoworkbench.domain.models import CustomFormulaDefinition, Dataset


class CustomFormulaError(ValueError):
    pass


_MNEMONIC = re.compile(r"^[A-Z][A-Z0-9_]{0,63}$")
_BINARY = {
    ast.Add: operator.add, ast.Sub: operator.sub, ast.Mult: operator.mul,
    ast.Div: operator.truediv, ast.Pow: operator.pow,
}
_UNARY = {ast.UAdd: operator.pos, ast.USub: operator.neg}
_FUNCTIONS = {
    "abs": np.abs, "sqrt": np.sqrt, "log10": np.log10,
    "minimum": np.minimum, "maximum": np.maximum,
}


def formula_inputs(expression: str) -> tuple[str, ...]:
    tree = _parse(expression)
    _validate(tree)
    names = {
        node.id.upper()
        for node in ast.walk(tree)
        if isinstance(node, ast.Name) and node.id.casefold() not in _FUNCTIONS
    }
    return tuple(sorted(names))


def evaluate_formula(expression: str, inputs: Mapping[str, Array]) -> Array:
    tree = _parse(expression)
    _validate(tree)
    normalized = {name.upper(): np.asarray(values, dtype=np.float64) for name, values in inputs.items()}
    required = formula_inputs(expression)
    missing = set(required) - set(normalized)
    if missing:
        raise CustomFormulaError(f"Отсутствуют входные кривые: {', '.join(sorted(missing))}")
    shapes = {normalized[name].shape for name in required}
    if not required or len(shapes) != 1:
        raise CustomFormulaError("Формула должна использовать кривые одинаковой формы")
    with np.errstate(all="ignore"):
        result = np.asarray(_evaluate(tree.body, normalized), dtype=np.float64)
    expected_shape = normalized[required[0]].shape
    if result.shape != expected_shape:
        result = np.full(expected_shape, float(result), dtype=np.float64)
    result[~np.isfinite(result)] = np.nan
    return result


def calculate_custom_formula(dataset: Dataset, definition: CustomFormulaDefinition) -> Array:
    inputs: dict[str, Array] = {}
    for mnemonic in formula_inputs(definition.expression):
        curve = dataset.curve_by_mnemonic(mnemonic)
        if curve is None:
            raise CustomFormulaError(f"В dataset отсутствует кривая {mnemonic}")
        inputs[mnemonic] = curve.values
    return evaluate_formula(definition.expression, inputs)


def validate_definition(definition: CustomFormulaDefinition) -> tuple[str, ...]:
    if not definition.formula_id.strip() or not definition.name.strip():
        raise CustomFormulaError("ID и название формулы обязательны")
    output = definition.output_mnemonic.strip().upper()
    if not _MNEMONIC.fullmatch(output):
        raise CustomFormulaError("Некорректная выходная мнемоника")
    inputs = formula_inputs(definition.expression)
    invalid_inputs = [name for name in inputs if not _MNEMONIC.fullmatch(name)]
    if invalid_inputs:
        raise CustomFormulaError(f"Некорректные входные мнемоники: {', '.join(invalid_inputs)}")
    if output in inputs:
        raise CustomFormulaError("Выходная кривая не может быть входом собственной формулы")
    return inputs


def _parse(expression: str) -> ast.Expression:
    if not expression.strip() or len(expression) > 2000:
        raise CustomFormulaError("Формула пуста или превышает 2000 символов")
    try:
        return ast.parse(expression, mode="eval")
    except SyntaxError as exc:
        raise CustomFormulaError("Синтаксическая ошибка формулы") from exc


def _validate(tree: ast.AST) -> None:
    allowed = (ast.Expression, ast.BinOp, ast.UnaryOp, ast.Name, ast.Load, ast.Constant, ast.Call)
    for node in ast.walk(tree):
        if isinstance(node, (ast.operator, ast.unaryop)):
            continue
        if not isinstance(node, allowed):
            raise CustomFormulaError(f"Запрещённая конструкция: {type(node).__name__}")
        if isinstance(node, ast.BinOp) and type(node.op) not in _BINARY:
            raise CustomFormulaError("Оператор не поддерживается")
        if isinstance(node, ast.UnaryOp) and type(node.op) not in _UNARY:
            raise CustomFormulaError("Унарный оператор не поддерживается")
        if isinstance(node, ast.Call):
            if not isinstance(node.func, ast.Name) or node.func.id.casefold() not in _FUNCTIONS:
                raise CustomFormulaError("Функция не поддерживается")
            if node.keywords:
                raise CustomFormulaError("Именованные аргументы запрещены")
        if isinstance(node, ast.Constant) and (
            isinstance(node.value, bool) or not isinstance(node.value, (int, float))
        ):
            raise CustomFormulaError("Разрешены только числовые константы")


def _evaluate(node: ast.AST, inputs: Mapping[str, Array]) -> Array | float:
    if isinstance(node, ast.Name):
        return inputs[node.id.upper()]
    if isinstance(node, ast.Constant):
        return float(cast(int | float, node.value))
    if isinstance(node, ast.BinOp):
        operation = cast(Callable[[Any, Any], Any], _BINARY[type(node.op)])
        return operation(_evaluate(node.left, inputs), _evaluate(node.right, inputs))
    if isinstance(node, ast.UnaryOp):
        unary_operation = cast(Callable[[Any], Any], _UNARY[type(node.op)])
        return unary_operation(_evaluate(node.operand, inputs))
    if isinstance(node, ast.Call) and isinstance(node.func, ast.Name):
        function = _FUNCTIONS[node.func.id.casefold()]
        return function(*(_evaluate(argument, inputs) for argument in node.args))
    raise CustomFormulaError("Формулу невозможно вычислить")
