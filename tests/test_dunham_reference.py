from __future__ import annotations

from hashlib import sha256
from pathlib import Path

import fitz
from PySide6.QtPdf import QPdfDocument
from PySide6.QtPdfWidgets import QPdfView

from geoworkbench.project.lithotype_catalog_controller import LithotypeCatalogController
from geoworkbench.project.session import ProjectSession
from geoworkbench.services.localization import AppLanguage
from geoworkbench.ui.lithotype_catalog_dialog import LithotypeCatalogDialog


ROOT = Path(__file__).resolve().parents[1]
REFERENCE = (
    ROOT
    / "src/geoworkbench/resources/reference/dunham_classification_ru_kk_en.pdf"
)

_ORIGINAL_IMAGE_HASHES = {
    "0c718a551fb6a943ae915ac32a5bd7a0cd4879a13699b33886be55545080e739",
    "12498989b88256af4242415bd422141b2fd3aeb29611caac024f269a1e649ed9",
    "15ecd63814d27caf2cd1707011ed4ab88bc49155d9692873298f8aca2ff53f0e",
    "475561fe564db96f6c50ed0daf88c8d49ccba8637897c1b82807d9161bc8b573",
    "56ceab63bf131968f5ac03d1742aa9a1df54386f0e2dcbb3c1cee8dc5bd826ba",
    "873e3357c307c784eeec60f4c89e612cb3fd8831a608d88f9a3536b73840287e",
    "937f63aba9dfbe4bcd516899b0d2b00d82ba7c2d5e6b60663ac89bb4ac4d9937",
}


def test_dunham_reference_preserves_all_five_source_pages_and_content() -> None:
    document = fitz.open(REFERENCE)

    assert document.page_count == 5
    page_text = [page.get_text() for page in document]
    assert "Классификация карбонатных пород по Данэму" in page_text[0]
    assert "Mudstone" in page_text[1] and "Wackestone" in page_text[1]
    assert "Packstone" in page_text[2] and "Grainstone" in page_text[2]
    assert "Floatstone" in page_text[3] and "Rudstone" in page_text[3]
    assert "Additional classes and practical use" in page_text[4]
    assert "Dunham, R.J. (1962)" in page_text[4]
    assert "CC BY-SA 4.0" in page_text[4]


def test_dunham_reference_preserves_original_photo_streams() -> None:
    document = fitz.open(REFERENCE)
    image_xrefs = {image[0] for page in document for image in page.get_images(full=True)}
    image_hashes = {
        sha256(document.xref_stream_raw(xref)).hexdigest() for xref in image_xrefs
    }

    # Six rock photographs plus the original page logo are retained byte-for-byte.
    assert image_hashes == _ORIGINAL_IMAGE_HASHES


def test_lithotype_reference_dialog_exposes_dunham_section(qapp) -> None:
    dialog = LithotypeCatalogDialog(
        LithotypeCatalogController(ProjectSession()),
        language=AppLanguage.RU,
    )
    qapp.processEvents()

    assert dialog.sections.count() == 3
    assert dialog.sections.tabText(0) == "Коды пород LAS"
    assert dialog.sections.tabText(1) == "Литотипы"
    assert dialog.sections.tabText(2) == "Классификация Данэма"
    assert dialog.dunham_reference.document.status() is QPdfDocument.Status.Ready
    assert dialog.dunham_reference.document.pageCount() == 5
    assert dialog.dunham_reference.view.pageMode() is QPdfView.PageMode.MultiPage
    assert dialog.dunham_reference.view.zoomMode() is QPdfView.ZoomMode.FitToWidth
    dialog.close()


def test_dunham_tab_title_follows_interface_language(qapp) -> None:
    dialog = LithotypeCatalogDialog(
        LithotypeCatalogController(ProjectSession()),
        language=AppLanguage.EN,
    )

    assert dialog.sections.tabText(2) == "Dunham classification"
    assert dialog.dunham_reference.fit_width_button.text() == "Fit width"
    dialog.close()
