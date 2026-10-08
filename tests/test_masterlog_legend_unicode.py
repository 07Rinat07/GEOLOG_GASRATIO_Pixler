from copy import deepcopy

import fitz
import pytest
from PySide6.QtCore import QRectF
from PySide6.QtGui import QFont, QPainter, QPdfWriter

from geoworkbench.printing import masterlog_renderer as renderer
from geoworkbench.printing.lba_visuals import LBA_TYPE_STYLES, lba_intensity_name
from geoworkbench.printing.masterlog_output import MasterlogOutputSettings
from geoworkbench.printing.unicode_support import resolve_unicode_font_profile
from geoworkbench.services.localization import AppLanguage
from geoworkbench.tablet.lithology_legend import LithologyLegendEntry
from geoworkbench.domain.models import MasterlogHeaderElement
from geoworkbench.project.controller import ProjectController
from test_masterlog_control_layout import controlled_form


@pytest.mark.parametrize("language", list(AppLanguage))
@pytest.mark.parametrize("dpi", [72, 96, 144, 300, 600])
@pytest.mark.parametrize("kind", ["lithology", "empty", "lba"])
def test_legend_pdf_uses_unicode_stack_and_physical_size(
    qapp, tmp_path, monkeypatch, language, dpi, kind
):
    original_ui_font = QFont(qapp.font())
    properties = {"font_size_mm": 3.0, "columns": 1, "color": "#123456"}
    before = deepcopy(properties)
    expected_body = {
        AppLanguage.RU: "Песчаник",
        AppLanguage.KK: "Құмтас Әә Ғғ Ққ Ңң Өө Ұұ Үү Һһ Іі",
        AppLanguage.EN: "Sandstone",
    }[language]
    entries = (LithologyLegendEntry("rock", "SS", expected_body, "#ffeeaa", "sandstone"),)
    fonts = []
    original_print_font = renderer.print_font

    def capture_font(size, *, text, bold=False):
        font = original_print_font(size, text=text, bold=bold)
        fonts.append((text, font.families(), bold))
        return font

    monkeypatch.setattr(renderer, "print_font", capture_font)
    target = tmp_path / "legend.pdf"
    writer = QPdfWriter(str(target))
    writer.setResolution(dpi)
    painter = QPainter(writer)
    painter.scale(dpi / 25.4, dpi / 25.4)
    old_font, old_pen = painter.font(), painter.pen()
    try:
        qapp.setFont(QFont("Courier New", 19))
        if kind == "lba":
            renderer._paint_lba_legend(painter, QRectF(0, 0, 190, 65), properties, language)
        else:
            renderer._paint_lithology_legend(
                painter, QRectF(0, 0, 190, 30), entries if kind == "lithology" else (),
                properties, language,
            )
        assert painter.font() == old_font
        assert painter.pen() == old_pen
    finally:
        painter.end()
        qapp.setFont(original_ui_font)
    assert properties == before
    assert len(fonts) == 2
    assert fonts[0][2] and not fonts[1][2]
    for text, families, _ in fonts:
        assert families == list(resolve_unicode_font_profile(text).families)
    with fitz.open(target) as document:
        page = document[0]
        text = page.get_text()
        if kind == "lithology":
            assert expected_body in text
        elif kind == "empty":
            assert {
                AppLanguage.RU: "В выбранном интервале нет литологии",
                AppLanguage.KK: "Таңдалған аралықта литология жоқ",
                AppLanguage.EN: "No lithology in the selected interval",
            }[language] in text
        else:
            for style in LBA_TYPE_STYLES:
                assert style.localized_name(language) in text
            for intensity in range(1, 6):
                assert lba_intensity_name(intensity, language) in text
        body_sizes = [
            span["size"]
            for block in page.get_text("dict")["blocks"] if "lines" in block
            for line in block["lines"] for span in line["spans"]
            if span["text"].strip() and span["text"].strip() in fonts[1][0]
        ]
        assert body_sizes
        assert body_sizes == pytest.approx([3.0 * 72 / 25.4] * len(body_sizes), abs=0.08)


@pytest.mark.parametrize("language", list(AppLanguage))
def test_masterlog_legend_export_after_project_reopen(qapp, tmp_path, language):
    session, template = controlled_form()
    template.header_height_mm = 115
    template.header_elements = [
        MasterlogHeaderElement("rocks", "lithology_legend", 5, 5, 190, 25,
                               {"scope": "used", "font_size_mm": 3.0}),
        MasterlogHeaderElement("lba", "lba_legend", 5, 35, 190, 65,
                               {"font_size_mm": 3.0}),
    ]
    package = tmp_path / "legend.geologpkg"
    ProjectController(session=session).save_project(package)
    restored = ProjectController().open_project(package)
    saved = restored.project.masterlog_templates[template.template_id]
    before = deepcopy(saved)
    depth = restored.current_dataset.depth.copy()
    values = restored.current_dataset.curve_by_mnemonic("C1").values.copy()
    target = renderer.export_masterlog_pdf(
        saved, restored, tmp_path / "masterlog.pdf",
        settings=MasterlogOutputSettings(145, 155, language),
    )
    with fitz.open(target) as document:
        text = "".join(page.get_text() for page in document)
        assert {
            AppLanguage.RU: "В выбранном интервале нет литологии",
            AppLanguage.KK: "Таңдалған аралықта литология жоқ",
            AppLanguage.EN: "No lithology in the selected interval",
        }[language] in text
        for style in LBA_TYPE_STYLES:
            assert style.localized_name(language) in text
    assert saved == before
    import numpy as np

    np.testing.assert_array_equal(restored.current_dataset.depth, depth)
    np.testing.assert_array_equal(restored.current_dataset.curve_by_mnemonic("C1").values, values)
