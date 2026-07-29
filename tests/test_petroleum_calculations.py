from __future__ import annotations

from pathlib import Path
import zipfile

import fitz
import pytest

from geoworkbench.files.pdf_tools import PdfTools
from geoworkbench.files.petroleum_calculations import (
    annular_volume,
    circulation_time_minutes,
    equivalent_circulating_density,
    formation_elevations,
    hydrostatic_pressure,
    mixed_fluid_density,
    pipe_geometry,
)


def test_pipe_geometry_accepts_oilfield_fraction_notation() -> None:
    result = pipe_geometry("7 1/2\"", wall_thickness_mm=9.5, length_m=12.0)

    assert result.outer_diameter_mm == pytest.approx(190.5)
    assert result.inner_diameter_mm == pytest.approx(171.5)
    assert result.capacity_l_per_m > 0
    assert result.mass_kg_per_m > 0
    assert result.total_mass_kg == pytest.approx(result.mass_kg_per_m * 12.0)


def test_drilling_hydrostatic_annular_and_lag_calculations() -> None:
    pressure = hydrostatic_pressure(1_200.0, 2_500.0)
    annulus = annular_volume(215.9, 127.0, 1_000.0)
    minutes = circulation_time_minutes(annulus.volume_m3, 30.0)

    assert pressure.pressure_mpa == pytest.approx(29.41995)
    assert annulus.volume_m3 > 0
    assert minutes > 0


def test_mud_and_geology_calculations() -> None:
    ecd = equivalent_circulating_density(1_200.0, 2.5, 2_500.0)
    mixture = mixed_fluid_density(10.0, 1_200.0, 5.0, 1_000.0)
    elevations = formation_elevations(135.0, 2_200.0, 2_250.0)

    assert ecd > 1_200.0
    assert mixture == pytest.approx(1_133.3333333333)
    assert elevations.top_elevation_m == pytest.approx(-2_065.0)
    assert elevations.bottom_elevation_m == pytest.approx(-2_115.0)
    assert elevations.vertical_thickness_m == pytest.approx(50.0)


def test_pdf_visual_docx_contains_one_page_image_per_pdf_page(tmp_path: Path) -> None:
    source = tmp_path / "source.pdf"
    document = fitz.open()
    try:
        for page_number in range(2):
            page = document.new_page()
            page.insert_text((72, 72), f"PAGE {page_number + 1}")
            page.draw_rect(fitz.Rect(60, 100, 300, 250), color=(0, 0, 1))
        document.save(source)
    finally:
        document.close()

    target = PdfTools.export_pages_docx(source, tmp_path / "visual.docx")

    with zipfile.ZipFile(target) as archive:
        names = set(archive.namelist())
        document_xml = archive.read("word/document.xml").decode("utf-8")
        relationships = archive.read("word/_rels/document.xml.rels").decode("utf-8")
    assert "word/media/page_0001.png" in names
    assert "word/media/page_0002.png" in names
    assert document_xml.count("<w:drawing>") == 2
    assert relationships.count("relationships/image") == 2
