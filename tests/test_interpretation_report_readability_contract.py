from pathlib import Path


def test_pdf_keeps_geology_legend_and_methodology_on_separate_pages() -> None:
    source = Path(
        "src/geoworkbench/printing/hydrocarbon_interpretation_pdf_renderer.py"
    ).read_text(encoding="utf-8")

    legend_draw = source.index("paint_geology_legend(")
    legend_end = source.index("legend_painted = True", legend_draw)
    methodology = source.index("render_report_html(", legend_end)
    boundary = source[legend_end:methodology]

    assert "canvas.new_page()" in boundary
    assert "if legend_painted or canvas.has_content:" in boundary


def test_report_ratio_visual_contract_is_not_density_scatter() -> None:
    whole = Path(
        "src/geoworkbench/printing/hydrocarbon_interpretation_chart.py"
    ).read_text(encoding="utf-8")
    pdf = Path(
        "src/geoworkbench/printing/hydrocarbon_interpretation_pdf_chart.py"
    ).read_text(encoding="utf-8")
    enhanced = Path(
        "src/geoworkbench/printing/hydrocarbon_interpretation_pdf_chart_enhanced.py"
    ).read_text(encoding="utf-8")

    assert 'point_series = panel_name == "opus"' in whole
    assert 'line_width = 1.35 if panel_name == "ratios"' in whole
    assert 'line_width=0.82 if panel_name == "ratios"' in pdf
    assert 'point_series=panel_name == "opus"' in pdf
    assert 'point_series=panel_name == "opus"' in enhanced
