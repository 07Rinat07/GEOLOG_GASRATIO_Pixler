from __future__ import annotations

from pathlib import Path
import re


ROOT = Path(".")


def replace_once(path: str, old: str, new: str) -> None:
    target = ROOT / path
    text = target.read_text(encoding="utf-8")
    count = text.count(old)
    if count != 1:
        raise RuntimeError(
            f"{path}: expected one replacement, found {count}: {old[:120]!r}"
        )
    target.write_text(text.replace(old, new, 1), encoding="utf-8")


def replace_regex_once(path: str, pattern: str, replacement: str) -> None:
    target = ROOT / path
    text = target.read_text(encoding="utf-8")
    updated, count = re.subn(pattern, replacement, text, count=1, flags=re.DOTALL)
    if count != 1:
        raise RuntimeError(f"{path}: expected one regex replacement, found {count}")
    target.write_text(updated, encoding="utf-8")


def create_continuity_module() -> None:
    Path("src/geoworkbench/calculations/curve_continuity.py").write_text(
        '''from __future__ import annotations

from dataclasses import dataclass

import numpy as np
from numpy.typing import NDArray


FloatArray = NDArray[np.float64]
BoolArray = NDArray[np.bool_]


@dataclass(frozen=True, slots=True)
class CurveContinuityPolicy:
    """One conservative continuity contract for calculations and rendering.

    Only bounded missing rows compatible with the normal source cadence may be
    interpolated. Long acquisition outages, leading/trailing holes and measured
    finite zero values remain explicit evidence in the conditioned arrays.
    """

    max_gap_steps: float = 4.0
    cadence_factor: float = 2.5
    minimum_finite_samples: int = 2
    absolute_max_gap: float | None = None

    def __post_init__(self) -> None:
        if not np.isfinite(self.max_gap_steps) or self.max_gap_steps <= 0.0:
            raise ValueError("max_gap_steps должен быть положительным конечным числом")
        if not np.isfinite(self.cadence_factor) or self.cadence_factor <= 0.0:
            raise ValueError("cadence_factor должен быть положительным конечным числом")
        if self.minimum_finite_samples < 2:
            raise ValueError("minimum_finite_samples должен быть не меньше 2")
        if self.absolute_max_gap is not None and (
            not np.isfinite(self.absolute_max_gap) or self.absolute_max_gap <= 0.0
        ):
            raise ValueError("absolute_max_gap должен быть положительным конечным числом")


def _as_1d_float(values: FloatArray, *, name: str) -> FloatArray:
    array = np.asarray(values, dtype=np.float64)
    if array.ndim != 1:
        raise ValueError(f"{name} должен быть одномерным массивом")
    return array


def nominal_axis_step(axis: FloatArray) -> float | None:
    """Return the robust dense positive step of a monotonic engineering axis."""

    values = _as_1d_float(axis, name="Шкала")
    if values.size < 2:
        return None
    deltas = np.abs(np.diff(values))
    positive = np.sort(deltas[np.isfinite(deltas) & (deltas > 0.0)])
    if positive.size == 0:
        return None
    dense_half = positive[: max(1, (positive.size + 1) // 2)]
    step = float(np.median(dense_half))
    return step if np.isfinite(step) and step > 0.0 else None


def estimate_short_gap_limit(
    axis: FloatArray,
    values: FloatArray,
    *,
    nominal_step: float | None = None,
    policy: CurveContinuityPolicy | None = None,
) -> float | None:
    """Estimate the largest physical hole eligible for interpolation."""

    resolved = policy or CurveContinuityPolicy()
    axis_array = _as_1d_float(axis, name="Шкала")
    value_array = _as_1d_float(values, name="Кривая")
    if axis_array.shape != value_array.shape:
        raise ValueError("Шкала и значения кривой должны иметь одинаковую форму")

    finite_positions = np.flatnonzero(
        np.isfinite(axis_array) & np.isfinite(value_array)
    )
    if finite_positions.size < resolved.minimum_finite_samples:
        return None
    observed = np.abs(np.diff(axis_array[finite_positions]))
    observed = np.sort(observed[np.isfinite(observed) & (observed > 0.0)])
    if observed.size == 0:
        return None
    dense_half = observed[: max(1, (observed.size + 1) // 2)]
    normal_curve_step = float(np.median(dense_half))
    base_step = nominal_step if nominal_step is not None else nominal_axis_step(axis_array)
    candidates = [normal_curve_step * resolved.cadence_factor]
    if base_step is not None and np.isfinite(base_step) and base_step > 0.0:
        candidates.append(float(base_step) * resolved.max_gap_steps)
    limit = max(candidates)
    if resolved.absolute_max_gap is not None:
        limit = min(limit, resolved.absolute_max_gap)
    return limit if np.isfinite(limit) and limit > 0.0 else None


def interpolate_monotonic_unique(
    axis: FloatArray,
    values: FloatArray,
    *,
    max_gap: float,
) -> FloatArray:
    """Interpolate bounded missing rows on an increasing unique axis."""

    axis_array = _as_1d_float(axis, name="Шкала")
    output = _as_1d_float(values, name="Кривая").copy()
    if axis_array.shape != output.shape:
        raise ValueError("Шкала и значения кривой должны иметь одинаковую форму")
    if not np.isfinite(max_gap) or max_gap <= 0.0:
        raise ValueError("max_gap должен быть положительным конечным числом")
    if axis_array.size < 3:
        return output
    if not np.all(np.isfinite(axis_array)) or not np.all(np.diff(axis_array) > 0.0):
        raise ValueError("Шкала интерполяции должна строго возрастать")

    finite_positions = np.flatnonzero(np.isfinite(output))
    for left, right in zip(finite_positions[:-1], finite_positions[1:], strict=True):
        left_index = int(left)
        right_index = int(right)
        if right_index - left_index <= 1:
            continue
        distance = float(axis_array[right_index] - axis_array[left_index])
        if distance > max_gap:
            continue
        interior = slice(left_index + 1, right_index)
        missing = ~np.isfinite(output[interior])
        if not np.any(missing):
            continue
        interpolated = np.interp(
            axis_array[interior],
            (axis_array[left_index], axis_array[right_index]),
            (output[left_index], output[right_index]),
        )
        interior_values = output[interior]
        interior_values[missing] = interpolated[missing]
        output[interior] = interior_values
    return output


def interpolate_bounded_gaps(
    axis: FloatArray,
    values: FloatArray,
    *,
    max_gap: float,
) -> tuple[FloatArray, BoolArray]:
    """Interpolate bounded holes while preserving input order and evidence."""

    source_axis = _as_1d_float(axis, name="Глубина")
    source_values = _as_1d_float(values, name="Кривая")
    if source_axis.shape != source_values.shape:
        raise ValueError("Глубина и кривая должны иметь одинаковую длину")
    if source_axis.size < 2:
        raise ValueError("Для интерполяции нужны минимум две отметки глубины")
    if not np.all(np.isfinite(source_axis)):
        raise ValueError("Шкала глубины не должна содержать NaN или бесконечность")
    if not np.isfinite(max_gap) or max_gap <= 0.0:
        raise ValueError("max_gap должен быть положительным конечным числом")

    deltas = np.diff(source_axis)
    increasing = bool(np.all(deltas >= 0.0) and np.any(deltas > 0.0))
    decreasing = bool(np.all(deltas <= 0.0) and np.any(deltas < 0.0))
    if not increasing and not decreasing:
        raise ValueError(
            "Шкала глубины должна быть монотонной; повторяющиеся отметки разрешены"
        )

    working_axis = source_axis[::-1] if decreasing else source_axis
    working_values = source_values[::-1] if decreasing else source_values
    normalized = working_values.astype(np.float64, copy=True)
    normalized[~np.isfinite(normalized)] = np.nan

    unique_axis, inverse = np.unique(working_axis, return_inverse=True)
    finite = np.isfinite(normalized)
    collapsed = np.full(unique_axis.shape, np.nan, dtype=np.float64)
    if np.any(finite):
        sums = np.bincount(
            inverse[finite],
            weights=normalized[finite],
            minlength=unique_axis.size,
        ).astype(np.float64, copy=False)
        counts = np.bincount(
            inverse[finite],
            minlength=unique_axis.size,
        )
        np.divide(sums, counts, out=collapsed, where=counts > 0)

    conditioned_unique = interpolate_monotonic_unique(
        unique_axis,
        collapsed,
        max_gap=max_gap,
    )
    replacement = conditioned_unique[inverse]
    output = normalized.copy()
    mask = ~np.isfinite(output) & np.isfinite(replacement)
    output[mask] = replacement[mask]
    if decreasing:
        return output[::-1].copy(), mask[::-1].astype(np.bool_, copy=True)
    return output, mask.astype(np.bool_, copy=False)


def build_segment_connect_mask(axis: FloatArray, values: FloatArray) -> BoolArray:
    """Return PyQtGraph connectivity: mask[i] joins point i to point i+1.

    The final entry is always false because it has no following point. Explicit
    NaN separators produced before downsampling therefore remain hard segment
    boundaries, while every finite continuous segment is rendered as a line.
    """

    axis_array = _as_1d_float(axis, name="Шкала")
    value_array = _as_1d_float(values, name="Кривая")
    if axis_array.shape != value_array.shape:
        raise ValueError("Шкала и значения кривой должны иметь одинаковую форму")
    connect = np.zeros(axis_array.shape, dtype=np.bool_)
    if axis_array.size < 2:
        return connect
    finite = np.isfinite(axis_array) & np.isfinite(value_array)
    delta = np.diff(axis_array)
    connect[:-1] = (
        finite[:-1]
        & finite[1:]
        & np.isfinite(delta)
        & (delta != 0.0)
    )
    return connect
''',
        encoding="utf-8",
    )


def patch_gas_conditioning() -> None:
    path = "src/geoworkbench/calculations/gas_conditioning.py"
    replace_once(
        path,
        "import numpy as np\n"
        "from numpy.typing import NDArray\n",
        "import numpy as np\n"
        "from numpy.typing import NDArray\n\n"
        "from geoworkbench.calculations.curve_continuity import (\n"
        "    CurveContinuityPolicy,\n"
        "    estimate_short_gap_limit,\n"
        "    interpolate_bounded_gaps,\n"
        "    interpolate_monotonic_unique,\n"
        ")\n",
    )
    replace_regex_once(
        path,
        r"@dataclass\(frozen=True, slots=True\)\nclass GasConditioningPolicy:.*?\n\n(?=@dataclass\(frozen=True, slots=True\)\nclass ConditionedGasComponents)",
        "GasConditioningPolicy = CurveContinuityPolicy\n\n\n",
    )
    replace_regex_once(
        path,
        r"def _component_gap_limit\(.*?\n\n(?=def _expand_conditioned_values)",
        "",
    )
    replace_regex_once(
        path,
        r"def interpolate_bounded_gaps\(.*?\n\n(?=def condition_gas_components)",
        "",
    )
    replace_once(
        path,
        "        limit = _component_gap_limit(\n"
        "            prepared.unique,\n"
        "            collapsed,\n"
        "            nominal_depth_step=prepared.nominal_step,\n"
        "            policy=resolved_policy,\n"
        "        )\n",
        "        limit = estimate_short_gap_limit(\n"
        "            prepared.unique,\n"
        "            collapsed,\n"
        "            nominal_step=prepared.nominal_step,\n"
        "            policy=resolved_policy,\n"
        "        )\n",
    )
    replace_once(
        path,
        "        conditioned_unique = _interpolate_unique_axis(\n",
        "        conditioned_unique = interpolate_monotonic_unique(\n",
    )


def patch_sampling() -> None:
    path = "src/geoworkbench/tablet/sampling.py"
    replace_once(
        path,
        "import numpy as np\n"
        "from numpy.typing import NDArray\n",
        "import numpy as np\n"
        "from numpy.typing import NDArray\n\n"
        "from geoworkbench.calculations.curve_continuity import (\n"
        "    CurveContinuityPolicy,\n"
        "    estimate_short_gap_limit,\n"
        "    interpolate_bounded_gaps,\n"
        "    nominal_axis_step,\n"
        ")\n",
    )
    replace_once(
        path,
        "_SHORT_GAP_AXIS_STEP_FACTOR = 4.0\n"
        "_SHORT_GAP_FINITE_STEP_FACTOR = 2.5\n",
        "_GAS_CONTINUITY_POLICY = CurveContinuityPolicy()\n",
    )
    replace_once(
        path,
        "    short_gap_limit = (\n"
        "        _short_gap_distance_limit(ordered_depth, ordered_values)\n"
        "        if bridge_short_gaps\n"
        "        else None\n"
        "    )\n"
        "    normal_step = _nominal_axis_step(ordered_depth)\n",
        "    short_gap_limit = (\n"
        "        estimate_short_gap_limit(\n"
        "            ordered_depth,\n"
        "            ordered_values,\n"
        "            policy=_GAS_CONTINUITY_POLICY,\n"
        "        )\n"
        "        if bridge_short_gaps\n"
        "        else None\n"
        "    )\n"
        "    if short_gap_limit is not None:\n"
        "        ordered_values, _interpolated = interpolate_bounded_gaps(\n"
        "            ordered_depth,\n"
        "            ordered_values,\n"
        "            max_gap=short_gap_limit,\n"
        "        )\n"
        "    normal_step = _nominal_axis_step(ordered_depth)\n",
    )
    replace_once(
        path,
        "    selected_values[~np.isfinite(selected_values)] = np.nan\n"
        "    if short_gap_limit is not None:\n"
        "        selected_values = interpolate_short_nan_gaps(\n"
        "            selected_depth,\n"
        "            selected_values,\n"
        "            max_gap=short_gap_limit,\n"
        "        )\n"
        "    if positive_values_only:\n",
        "    selected_values[~np.isfinite(selected_values)] = np.nan\n"
        "    if positive_values_only:\n",
    )
    replace_regex_once(
        path,
        r"def _short_gap_distance_limit\(.*?\n\n(?=def interpolate_short_nan_gaps)",
        '''def _short_gap_distance_limit(
    axis: NDArray[np.float64], values: NDArray[np.float64]
) -> float | None:
    return estimate_short_gap_limit(
        axis,
        values,
        policy=_GAS_CONTINUITY_POLICY,
    )


''',
    )
    replace_regex_once(
        path,
        r"def interpolate_short_nan_gaps\(.*?\n\n(?=def _collapse_duplicate_axis_samples)",
        '''def interpolate_short_nan_gaps(
    axis: NDArray[np.float64],
    values: NDArray[np.float64],
    *,
    max_gap: float | None = None,
) -> NDArray[np.float64]:
    axis_array = np.asarray(axis, dtype=np.float64)
    value_array = np.asarray(values, dtype=np.float64)
    if axis_array.shape != value_array.shape:
        raise ValueError(
            "Шкала глубины и значения кривой должны иметь одинаковую форму"
        )
    if value_array.size < 3:
        return value_array.copy()
    limit = (
        estimate_short_gap_limit(
            axis_array,
            value_array,
            policy=_GAS_CONTINUITY_POLICY,
        )
        if max_gap is None
        else float(max_gap)
    )
    if limit is None or not np.isfinite(limit) or limit <= 0.0:
        return value_array.copy()
    output, _mask = interpolate_bounded_gaps(
        axis_array,
        value_array,
        max_gap=limit,
    )
    return output


''',
    )
    replace_regex_once(
        path,
        r"def _nominal_axis_step\(axis: NDArray\[np\.float64\]\) -> float \| None:.*?\n\n(?=def _downsample_preserving_gaps)",
        '''def _nominal_axis_step(axis: NDArray[np.float64]) -> float | None:
    return nominal_axis_step(axis)


''',
    )


def patch_relative_gas() -> None:
    path = "src/geoworkbench/tablet/relative_gas.py"
    replace_once(
        path,
        "from geoworkbench.tablet.sampling import (\n",
        "from geoworkbench.calculations.curve_continuity import (\n"
        "    build_segment_connect_mask,\n"
        ")\n"
        "from geoworkbench.tablet.sampling import (\n",
    )
    replace_once(
        path,
        "    bands: tuple[RelativeGasBand, ...]\n",
        "    bands: tuple[RelativeGasBand, ...]\n"
        "    connect: NDArray[np.bool_]\n",
    )
    text = Path(path).read_text(encoding="utf-8")
    text = text.replace(
        "            bands=(),\n        )",
        "            bands=(),\n            connect=np.array([], dtype=np.bool_),\n        )",
    )
    text = text.replace(
        "                for name in names\n            ),\n        )",
        "                for name in names\n            ),\n            connect=np.array([], dtype=np.bool_),\n        )",
    )
    Path(path).write_text(text, encoding="utf-8")
    replace_once(
        path,
        "    return RelativeGasStack(selected_depth, baseline, tuple(bands))\n",
        "    connect = build_segment_connect_mask(selected_depth, baseline)\n"
        "    return RelativeGasStack(selected_depth, baseline, tuple(bands), connect)\n",
    )


def patch_tablet_view() -> None:
    path = "src/geoworkbench/tablet/tablet_view.py"
    replace_once(
        path,
        "from geoworkbench.tablet.geometry_cache import (\n"
        "    CurveGeometryCache,\n"
        "    CurveGeometryKey,\n"
        "    GeometryCacheStats,\n"
        ")\n",
        "from geoworkbench.tablet.geometry_cache import (\n"
        "    CurveGeometryCache,\n"
        "    CurveGeometryKey,\n"
        "    GeometryCacheStats,\n"
        "    is_gas_curve_id,\n"
        ")\n"
        "from geoworkbench.calculations.curve_continuity import (\n"
        "    build_segment_connect_mask,\n"
        ")\n",
    )
    replace_once(
        path,
        "            item.setData(normalized, visible_depth, connect=\"finite\")\n",
        "            connect: str | NDArray[np.bool_] = \"finite\"\n"
        "            if is_gas_curve_id(mnemonic):\n"
        "                connect = build_segment_connect_mask(visible_depth, normalized)\n"
        "            item.setData(normalized, visible_depth, connect=connect)\n",
    )
    replace_once(
        path,
        "            rendered.relative_baseline_item.setData(stack.baseline, stack.depth, connect=\"finite\")\n",
        "            rendered.relative_baseline_item.setData(\n"
        "                stack.baseline, stack.depth, connect=stack.connect\n"
        "            )\n",
    )
    replace_once(
        path,
        "                item.setData(band.upper, stack.depth, connect=\"finite\")\n",
        "                item.setData(band.upper, stack.depth, connect=stack.connect)\n",
    )


def create_tests() -> None:
    Path("tests/test_curve_continuity_policy.py").write_text(
        '''from __future__ import annotations

import numpy as np

from geoworkbench.calculations.curve_continuity import (
    CurveContinuityPolicy,
    build_segment_connect_mask,
    estimate_short_gap_limit,
    interpolate_bounded_gaps,
)
from geoworkbench.calculations.gas_conditioning import GasConditioningPolicy


def test_gas_conditioning_and_rendering_share_one_policy_type() -> None:
    assert GasConditioningPolicy is CurveContinuityPolicy


def test_common_policy_fills_sparse_cadence_and_keeps_long_outage() -> None:
    axis = np.arange(0.0, 31.0)
    values = np.full(axis.shape, np.nan)
    values[[0, 3, 6, 30]] = (10.0, 13.0, 16.0, 30.0)

    limit = estimate_short_gap_limit(axis, values)
    assert limit is not None
    conditioned, interpolated = interpolate_bounded_gaps(
        axis,
        values,
        max_gap=limit,
    )

    np.testing.assert_allclose(conditioned[:7], np.arange(10.0, 17.0))
    assert interpolated[1]
    assert interpolated[5]
    assert np.isnan(conditioned[15])
    assert not interpolated[15]


def test_segment_mask_joins_only_adjacent_finite_points() -> None:
    axis = np.arange(0.0, 7.0)
    values = np.array([1.0, 2.0, 3.0, np.nan, 5.0, 6.0, np.nan])

    connect = build_segment_connect_mask(axis, values)

    np.testing.assert_array_equal(
        connect,
        [True, True, False, False, True, False, False],
    )
    assert connect.dtype == np.bool_


def test_explicit_zero_remains_a_finite_linear_sample() -> None:
    axis = np.arange(0.0, 5.0)
    values = np.array([1.0, np.nan, 0.0, np.nan, 5.0])

    conditioned, mask = interpolate_bounded_gaps(axis, values, max_gap=3.0)

    assert conditioned[2] == 0.0
    assert not mask[2]
    assert conditioned[1] == 0.5
    assert conditioned[3] == 2.5
''',
        encoding="utf-8",
    )

    Path("tests/test_tablet_gas_segment_mask.py").write_text(
        '''from __future__ import annotations

import numpy as np

from geoworkbench.domain.models import (
    CurveData,
    CurveMetadata,
    Dataset,
    DatasetKind,
    DepthDomain,
)
from geoworkbench.tablet.models import TabletLayout, TrackDefinition, TrackKind
from geoworkbench.tablet.tablet_view import TabletView


def _view_with_sparse_gas() -> TabletView:
    depth = np.arange(1703.0, 1754.0, dtype=np.float64)
    values = np.full(depth.shape, np.nan)
    values[[0, 3, 6, 9, 12, 50]] = (10.0, 13.0, 16.0, 19.0, 22.0, 40.0)
    dataset = Dataset(
        "gas-mask-dataset",
        "Gas mask",
        DatasetKind.GTI,
        DepthDomain.MD,
        depth,
    )
    dataset.curves["curve-c1"] = CurveData(
        CurveMetadata(
            "curve-c1",
            "C1",
            "C1",
            "%",
            None,
            dataset.dataset_id,
        ),
        values,
    )
    view = TabletView()
    view.set_layout_model(
        TabletLayout(
            tracks=[
                TrackDefinition("depth", "Depth", TrackKind.DEPTH, width=120),
                TrackDefinition(
                    "gas",
                    "Gas",
                    TrackKind.GAS,
                    width=180,
                    curve_mnemonics=["C1"],
                ),
            ]
        )
    )
    view.resize(600, 800)
    view.set_dataset(dataset)
    view.set_visible_depth(1703.28, 1753.28)
    return view


def test_sparse_gas_plot_uses_explicit_segment_mask_without_symbols(qapp) -> None:
    view = _view_with_sparse_gas()
    qapp.processEvents()

    item = view._rendered["gas"].curve_items["C1"]
    x_values, y_values = item.getData()
    connect = item.curve.opts["connect"]

    assert x_values is not None and y_values is not None
    assert isinstance(connect, np.ndarray)
    assert connect.dtype == np.bool_
    assert connect.shape == y_values.shape
    assert np.count_nonzero(connect[:12]) >= 8
    assert not connect[-1]
    assert item.opts.get("symbol") is None
    view.close()


def test_viewport_inside_sparse_cadence_keeps_interpolated_line_context(qapp) -> None:
    view = _view_with_sparse_gas()
    view.set_visible_depth(1707.1, 1707.9)
    qapp.processEvents()

    item = view._rendered["gas"].curve_items["C1"]
    x_values, y_values = item.getData()
    connect = item.curve.opts["connect"]

    assert x_values is not None and y_values is not None
    assert len(y_values) >= 2
    assert np.count_nonzero(connect) >= 1
    assert np.all(np.isfinite(x_values[np.asarray(connect, dtype=bool)]))
    view.close()
''',
        encoding="utf-8",
    )


def update_docs() -> None:
    plan = Path("docs/PROJECT_PLAN.md")
    text = plan.read_text(encoding="utf-8")
    text = text.replace(
        "- [ ] **GAS-05:** устранить дублирование правил между calculation conditioning и render sampling:\n  вынести единый Qt-независимый continuity policy и единый segment mask для экрана, PDF,\n  preview и принтера.\n",
        "- [x] **GAS-05:** calculation conditioning и render sampling используют единый Qt-независимый `CurveContinuityPolicy`; gas-only viewport geometry кондиционируется до обрезки, а экран/PDF/preview/printer получают явный segment mask.\n",
    )
    text = text.replace(
        "- [ ] **RULER-04:** после стабилизации шкал завершить единый gas continuity/segment mask для C1–C5, relative gas, Haworth и Pixler.\n",
        "- [x] **RULER-04:** после стабилизации шкал внедрён единый gas continuity/segment mask для C1–C5, relative gas, Haworth и Pixler с сохранением длинных остановок и реальных нулей.\n",
    )
    plan.write_text(text, encoding="utf-8")

    architecture = Path("docs/ARCHITECTURE.md")
    text = architecture.read_text(encoding="utf-8")
    old = (
        "### Следующая граница\n\n"
        "Правило определения короткого gap пока представлено в calculation conditioning и в старом\n"
        "render sampling. Следующий безопасный рефакторинг вынесет общий immutable continuity policy и\n"
        "segment mask в Qt-независимый нижний слой. До этого calculation pipeline является источником\n"
        "истины для derived curves, а render policy не имеет права изменять Dataset.\n"
    )
    new = (
        "### Единая граница непрерывности\n\n"
        "`calculations/curve_continuity.py` является единственным источником правил cadence, bounded gap interpolation и segment connectivity. Calculation conditioning применяет его к immutable рабочим копиям C1–C5 до формул, а viewport sampling — к полному массиву до обрезки и downsampling. Renderer получает явный boolean connect mask; длинные остановки, края без данных и логарифмические нули остаются разрывами. Dataset и исходный LAS не изменяются.\n"
    )
    if old not in text:
        raise RuntimeError("ARCHITECTURE.md continuity anchor not found")
    architecture.write_text(text.replace(old, new, 1), encoding="utf-8")

    testing = Path("docs/TESTING.md")
    text = testing.read_text(encoding="utf-8")
    anchor = "## 13. Финальный критерий передачи\n"
    section = (
        "## 13. GAS-05: единый continuity policy и segment mask\n\n"
        "`tests/test_curve_continuity_policy.py`, `tests/test_gas_conditioning.py`, `tests/test_gas_curve_rendering_continuity.py` и `tests/test_tablet_gas_segment_mask.py` проверяют общий cadence policy, короткие и длинные пропуски, реальные нули, viewport/page context и явный PyQtGraph connect mask. Relative gas, Haworth, Pixler и source C1–C5 используют тот же экранный/печатный geometry path.\n\n"
        "```powershell\n"
        "python -m pytest -q tests/test_curve_continuity_policy.py tests/test_gas_conditioning.py tests/test_gas_curve_rendering_continuity.py tests/test_tablet_gas_segment_mask.py\n"
        "```\n\n"
        "## 14. Финальный критерий передачи\n"
    )
    if anchor not in text:
        raise RuntimeError("TESTING.md final section anchor not found")
    testing.write_text(text.replace(anchor, section, 1), encoding="utf-8")

    changelog = Path("docs/CHANGELOG.md")
    text = changelog.read_text(encoding="utf-8")
    anchor = "## Unreleased\n\n"
    addition = (
        "## Unreleased\n\n"
        "- Объединены calculation и render continuity rules: C1–C5 и производные газовые кривые кондиционируются на полном общем depth basis, короткие sparse updates образуют линии через явный segment mask, а длинные остановки и реальные нули сохраняются как разрывы.\n"
    )
    if anchor not in text:
        raise RuntimeError("CHANGELOG.md Unreleased anchor not found")
    changelog.write_text(text.replace(anchor, addition, 1), encoding="utf-8")


def main() -> None:
    create_continuity_module()
    patch_gas_conditioning()
    patch_sampling()
    patch_relative_gas()
    patch_tablet_view()
    create_tests()
    update_docs()


if __name__ == "__main__":
    main()
