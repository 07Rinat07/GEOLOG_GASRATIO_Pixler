from __future__ import annotations

from pathlib import Path


def replace_once(source: str, old: str, new: str, label: str) -> str:
    count = source.count(old)
    if count != 1:
        raise RuntimeError(f"{label}: expected one anchor, found {count}")
    return source.replace(old, new, 1)


def patch_complex_builder() -> None:
    path = Path("src/geoworkbench/forms/complex_gas.py")
    text = path.read_text(encoding="utf-8")
    start = text.index("    sections: list[tuple[str, FormColumn]] = [\n")
    end = text.index("\n\n    columns: list[FormColumn] = []", start)
    sections = '''    sections: list[tuple[str, FormColumn]] = [
        (
            "absolute",
            _curve_column(
                "column-complex-absolute",
                _t("absolute", lang),
                [
                    _binding(
                        "TG_CALC",
                        _t("absolute_sum", lang),
                        "%",
                        "#dc2626",
                        x_min=0.0,
                        x_max=100.0,
                        width=2.2,
                    ),
                    *_component_bindings(
                        lang,
                        unit="%",
                        x_min=0.0,
                        x_max=100.0,
                    ),
                ],
                gas_group,
                width=480,
                x_axis_label="%",
            ),
        ),
        (
            "normalized",
            _curve_column(
                "column-complex-normalized-components",
                _t("normalized_components", lang),
                [
                    _binding(
                        "TG_NORM",
                        _t("normalized_total", lang),
                        "norm",
                        "#7c3aed",
                        x_min=None,
                        x_max=None,
                        width=2.2,
                    ),
                    *_normalized_bindings(lang),
                ],
                gas_group,
                width=500,
                x_axis_label="norm",
            ),
        ),
        (
            "relative",
            _curve_column(
                "column-complex-relative",
                _t("relative", lang),
                _relative_bindings(lang),
                gas_group,
                width=480,
                x_axis_label="% ΣC1–C5",
            ),
        ),
        (
            "ratios",
            _curve_column(
                "column-complex-ratios",
                _t("ratios", lang),
                _ratio_bindings(lang),
                gas_group,
                width=400,
                x_axis_label="ratio",
            ),
        ),
        (
            "pixler",
            _curve_column(
                "column-complex-pixler",
                _t("pixler", lang),
                _pixler_bindings(),
                gas_group,
                width=380,
                x_axis_label="ratio (log)",
            ),
        ),
    ]'''
    text = text[:start] + sections + text[end:]
    text = text.replace('"normalized gas units",\n                color,', '"norm",\n                color,')
    path.write_text(text, encoding="utf-8")


def patch_a4_catalog() -> None:
    path = Path("src/geoworkbench/forms/a4_factory_templates.py")
    text = path.read_text(encoding="utf-8")
    import_anchor = (
        "from geoworkbench.forms.models import "
        "FormAxisKind, FormDocument, ParameterBinding\n"
    )
    import_line = "from geoworkbench.forms.complex_gas import complex_gas_form\n"
    if import_line not in text:
        text = replace_once(text, import_anchor, import_line + import_anchor, "builder import")

    start = text.index(
        "def _complex_gas(language: TemplateLanguage, orientation: str) -> FormDocument:\n"
    )
    end = text.index('\ndef a4_factory_templates(language: str = "ru")', start)
    function = '''def _complex_gas(language: TemplateLanguage, orientation: str) -> FormDocument:
    """Build the complete C1-C5 form with an internal depth scale per graph."""

    landscape = orientation == "landscape"
    form = complex_gas_form(language)
    form.form_id = f"factory-complex-gas-a4-{orientation}"
    form.name = _name("complex_gas", language, orientation)

    depth_width = 55 if landscape else 48
    graph_widths = (
        (150, 140, 145, 140, 140)
        if landscape
        else (96, 90, 90, 82, 82)
    )
    graph_index = 0
    for column in form.columns:
        if column.tracks and column.tracks[0].kind is TrackKind.DEPTH:
            column.width = depth_width
        else:
            column.width = graph_widths[graph_index]
            graph_index += 1

    if graph_index != len(graph_widths):
        raise RuntimeError("Unexpected complex-gas column structure")
    return _finalize(form, "gas_interpretation", orientation)

'''
    path.write_text(text[:start] + function + text[end + 1 :], encoding="utf-8")


def patch_package_export() -> None:
    path = Path("src/geoworkbench/forms/__init__.py")
    text = path.read_text(encoding="utf-8")
    import_line = "from geoworkbench.forms.complex_gas import complex_gas_form\n"
    if import_line not in text:
        text = replace_once(
            text,
            "from geoworkbench.forms.models import (\n",
            import_line + "from geoworkbench.forms.models import (\n",
            "package import",
        )
    if '    "complex_gas_form",\n' not in text:
        text = replace_once(
            text,
            '    "build_masterlog_from_form",\n',
            '    "build_masterlog_from_form",\n    "complex_gas_form",\n',
            "package export",
        )
    path.write_text(text, encoding="utf-8")


def patch_documentation() -> None:
    path = Path("docs/COMPLEX_GAS_FORM.md")
    text = path.read_text(encoding="utf-8")
    text = text.replace(
        "Заводская форма `factory-complex-gas-analysis` предназначена",
        "Заводские формы `factory-complex-gas-a4-portrait` и "
        "`factory-complex-gas-a4-landscape` предназначены",
    )
    text = text.replace(
        "Перед каждой из семи графических колонок",
        "Перед каждой из пяти графических колонок",
    )
    path.write_text(text, encoding="utf-8")


def patch_existing_a4_test() -> None:
    path = Path("tests/test_a4_factory_templates.py")
    text = path.read_text(encoding="utf-8")
    start = text.index(
        "def test_complex_gas_factory_contains_all_requested_gas_groups() -> None:\n"
    )
    end = text.index(
        "\ndef test_legacy_forms_remain_resolvable_but_are_hidden()", start
    )
    test = '''def test_complex_gas_factory_contains_all_requested_gas_groups() -> None:
    form = a4_factory_templates("ru")["factory-complex-gas-a4-landscape"]
    graph_columns = form.columns[1::2]
    canonical_ids = {
        binding.canonical_parameter_id
        for column in form.columns
        for track in column.tracks
        for binding in track.bindings
    }

    assert len(form.columns) == 10
    assert all(
        form.columns[index].tracks[0].kind.value == "depth"
        and form.columns[index + 1].tracks[0].kind.value == "curve"
        for index in range(0, len(form.columns), 2)
    )
    assert [column.title for column in graph_columns] == [
        "Абсолютные компоненты",
        "Нормализованные компоненты",
        "Относительный газ",
        "Wetness, Balance, Character и изомеры",
        "Коэффициенты Pixler",
    ]
    assert {
        "TG_CALC",
        "C1",
        "C2",
        "C3",
        "IC4",
        "NC4",
        "IC5",
        "NC5",
        "TG_NORM",
        "C1_NORM_REF",
        "C2_NORM",
        "C3_NORM",
        "IC4_NORM",
        "NC4_NORM",
        "IC5_NORM",
        "NC5_NORM",
        "C1_REL",
        "C2_REL",
        "C3_REL",
        "IC4_REL",
        "NC4_REL",
        "IC5_REL",
        "NC5_REL",
        "WETNESS",
        "BALANCE",
        "CHARACTER",
        "IC4_NC4",
        "IC5_NC5",
        "PIXLER_C1_C2",
        "PIXLER_C1_C3",
        "PIXLER_C1_C4",
        "PIXLER_C1_C5",
    } <= canonical_ids

'''
    path.write_text(text[:start] + test + text[end + 1 :], encoding="utf-8")


def write_regression_tests() -> None:
    Path("tests/test_complex_gas_form.py").write_text(
        '''from __future__ import annotations

import numpy as np

from geoworkbench.calculations.gas_ratio import calculate_basic_ratios
from geoworkbench.forms.a4_factory_templates import a4_factory_templates
from geoworkbench.forms.complex_gas import complex_gas_form
from geoworkbench.printing.form_width_advisor import FormWidthLevel, audit_form_width
from geoworkbench.tablet.models import TrackKind, XScale

SEVEN_COMPONENTS = ("C1", "C2", "C3", "IC4", "NC4", "IC5", "NC5")


def _track(form, track_id: str):
    return next(
        track
        for column in form.columns
        for track in column.tracks
        if track.track_id == track_id
    )


def _assert_layout(form, depth_width: int) -> None:
    assert len(form.columns) == 10
    assert all(
        form.columns[index].tracks[0].kind is TrackKind.DEPTH
        and form.columns[index + 1].tracks[0].kind is TrackKind.CURVE
        for index in range(0, len(form.columns), 2)
    )
    depth_columns = form.columns[::2]
    assert len({column.column_id for column in depth_columns}) == 5
    assert len({column.tracks[0].track_id for column in depth_columns}) == 5
    assert all(column.width == depth_width for column in depth_columns)
    assert all(column.tracks[0].show_interval_labels for column in depth_columns)


def test_builder_contains_every_requested_curve() -> None:
    form = complex_gas_form("ru")
    _assert_layout(form, 96)

    absolute = _track(form, "track-column-complex-absolute")
    assert tuple(binding.canonical_parameter_id for binding in absolute.bindings) == (
        "TG_CALC",
        *SEVEN_COMPONENTS,
    )
    assert all(binding.unit == "%" for binding in absolute.bindings)

    normalized = _track(form, "track-column-complex-normalized-components")
    assert tuple(binding.canonical_parameter_id for binding in normalized.bindings) == (
        "TG_NORM",
        "C1_NORM_REF",
        "C2_NORM",
        "C3_NORM",
        "IC4_NORM",
        "NC4_NORM",
        "IC5_NORM",
        "NC5_NORM",
    )
    assert all(binding.unit == "norm" for binding in normalized.bindings)

    relative = _track(form, "track-column-complex-relative")
    assert tuple(binding.canonical_parameter_id for binding in relative.bindings) == tuple(
        f"{component}_REL" for component in SEVEN_COMPONENTS
    )

    ratios = _track(form, "track-column-complex-ratios")
    assert tuple(binding.canonical_parameter_id for binding in ratios.bindings) == (
        "WETNESS",
        "BALANCE",
        "CHARACTER",
        "IC4_NC4",
        "IC5_NC5",
    )
    assert ratios.bindings[0].x_scale is XScale.LINEAR
    assert all(binding.x_scale is XScale.LOGARITHMIC for binding in ratios.bindings[1:])

    pixler = _track(form, "track-column-complex-pixler")
    assert tuple(binding.canonical_parameter_id for binding in pixler.bindings) == (
        "PIXLER_C1_C2",
        "PIXLER_C1_C3",
        "PIXLER_C1_C4",
        "PIXLER_C1_C5",
    )
    assert all(binding.x_scale is XScale.LOGARITHMIC for binding in pixler.bindings)

    bindings = [
        binding
        for column in form.columns
        for track in column.tracks
        for binding in track.bindings
    ]
    assert all(binding.header_text_color == binding.style.color for binding in bindings)
    assert all(binding.header_line_color == binding.style.color for binding in bindings)


def test_both_a4_variants_fit_and_have_internal_depth_scales() -> None:
    forms = a4_factory_templates("ru")
    portrait = forms["factory-complex-gas-a4-portrait"]
    landscape = forms["factory-complex-gas-a4-landscape"]
    _assert_layout(portrait, 48)
    _assert_layout(landscape, 55)

    portrait_audit = audit_form_width(column.width for column in portrait.columns)
    landscape_audit = audit_form_width(column.width for column in landscape.columns)
    assert portrait_audit.level is FormWidthLevel.FITS_PORTRAIT
    assert landscape_audit.level is FormWidthLevel.FITS_LANDSCAPE


def test_split_isomers_take_priority_over_aggregate_c4_c5() -> None:
    results = calculate_basic_ratios(
        {
            "C1": np.array([80.0]),
            "C2": np.array([10.0]),
            "C3": np.array([5.0]),
            "IC4": np.array([1.0]),
            "NC4": np.array([2.0]),
            "IC5": np.array([1.0]),
            "NC5": np.array([1.0]),
            "C4": np.array([999.0]),
            "C5": np.array([999.0]),
        }
    )
    np.testing.assert_allclose(results["TG_CALC"].values, [100.0])
    relative_sum = sum(results[f"{name}_REL"].values for name in SEVEN_COMPONENTS)
    np.testing.assert_allclose(relative_sum, [100.0])
    np.testing.assert_allclose(results["WETNESS"].values, [20.0])
    np.testing.assert_allclose(results["BALANCE"].values, [9.0])
    np.testing.assert_allclose(results["CHARACTER"].values, [1.0])
    np.testing.assert_allclose(results["IC4_NC4"].values, [0.5])
    np.testing.assert_allclose(results["IC5_NC5"].values, [1.0])
    np.testing.assert_allclose(results["PIXLER_C1_C2"].values, [8.0])
    np.testing.assert_allclose(results["PIXLER_C1_C3"].values, [16.0])
    np.testing.assert_allclose(results["PIXLER_C1_C4"].values, [80.0 / 3.0])
    np.testing.assert_allclose(results["PIXLER_C1_C5"].values, [40.0])


def test_aggregate_c4_c5_are_supported_as_fallback() -> None:
    results = calculate_basic_ratios(
        {
            "C1": np.array([80.0]),
            "C2": np.array([10.0]),
            "C3": np.array([5.0]),
            "C4": np.array([3.0]),
            "C5": np.array([2.0]),
        }
    )
    np.testing.assert_allclose(results["TG_CALC"].values, [100.0])
    np.testing.assert_allclose(results["C4_REL"].values, [3.0])
    np.testing.assert_allclose(results["C5_REL"].values, [2.0])
    np.testing.assert_allclose(results["PIXLER_C1_C4"].values, [80.0 / 3.0])
    np.testing.assert_allclose(results["PIXLER_C1_C5"].values, [40.0])
''',
        encoding="utf-8",
    )


def remove_staging_files() -> None:
    for path in (
        Path(".github/workflows/apply-complex-gas-a4.yml"),
        Path(".github/workflows/run-complex-gas-a4-patch.yml"),
        Path("tools/apply_complex_gas_a4_patch.py"),
    ):
        path.unlink(missing_ok=True)


def main() -> None:
    patch_complex_builder()
    patch_a4_catalog()
    patch_package_export()
    patch_documentation()
    patch_existing_a4_test()
    write_regression_tests()
    remove_staging_files()


if __name__ == "__main__":
    main()
