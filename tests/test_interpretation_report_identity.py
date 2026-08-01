from __future__ import annotations

import zipfile
from xml.etree import ElementTree as ET

import fitz
import pytest
from PySide6.QtGui import QPageLayout

from geoworkbench.data.hydrocarbon_interpretation_export_docx_polished import (
    export_polished_hydrocarbon_interpretation_docx,
)
from geoworkbench.printing.hydrocarbon_interpretation_pdf_chart_enhanced import (
    major_depth_ticks,
    minor_depth_ticks,
)
from geoworkbench.printing.hydrocarbon_interpretation_pdf_layout import DepthPage
from geoworkbench.printing.hydrocarbon_interpretation_report import (
    export_hydrocarbon_interpretation_pdf,
)
from geoworkbench.printing.hydrocarbon_interpretation_report_identity import (
    InterpretationReportIdentity,
    default_interpretation_report_identity,
)
from geoworkbench.services.hydrocarbon_interpretation import (
    HydrocarbonInterpretationReport,
)
from geoworkbench.services.localization import AppLanguage
from geoworkbench.ui.interpretation_report_details_dialog import (
    InterpretationReportDetailsDialog,
)


_W_NS = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"
_W = {"w": _W_NS}


def _report() -> HydrocarbonInterpretationReport:
    return HydrocarbonInterpretationReport(
        project_name="Автоматический проект",
        well_name="Файл-скважина-494",
        dataset_id="dataset-1",
        dataset_name="Техническое_имя_загруженного_файла.las",
        generated_at="2026-08-01T11:30:00+05:00",
        depth_unit="m",
        threshold=3.0,
        primary_mnemonic="TG_NORM_CALC",
        baseline_median=None,
        robust_scale=None,
        methods=(),
        candidates=(),
        manual_intervals=(),
        warnings=(),
    )


def _manual_identity() -> InterpretationReportIdentity:
    return InterpretationReportIdentity(
        report_title="Отчёт ГТИ по скважине Северная-12",
        report_subtitle="Интерпретация газового каротажа",
        project_name="Проект Северный купол",
        well_name="Северная-12",
        field_name="Месторождение Северное",
        location="Блок 4, Казахстан",
        operator_name="АО Заказчик",
        contractor_name="ТОО Сервис ГТИ",
        rig_name="Буровая ZJ-70",
        dataset_name="Основной интервал газового каротажа",
        interval="1250.00–2860.00 m",
        document_number="GAS-INT-012",
        revision="02",
        document_status="Финальный",
        report_date="01.08.2026",
        prepared_by="Инженер ГТИ И.И.",
        checked_by="Ведущий геолог П.П.",
        approved_by="Руководитель проекта С.С.",
        confidentiality="Для служебного использования",
        remarks="Реквизиты введены вручную перед печатью.",
    )


def _word_text(element: ET.Element) -> str:
    return "".join(node.text or "" for node in element.findall(".//w:t", _W))


def test_default_identity_uses_loaded_values_only_as_initial_suggestion() -> None:
    identity = default_interpretation_report_identity(
        _report(),
        AppLanguage.RU,
        interval="1000.00–1200.00 m",
    )

    assert identity.project_name == "Автоматический проект"
    assert identity.well_name == "Файл-скважина-494"
    assert identity.dataset_name.endswith(".las")
    assert identity.interval == "1000.00–1200.00 m"
    assert identity.revision == "00"


def test_details_dialog_returns_manually_edited_values(qapp) -> None:
    defaults = default_interpretation_report_identity(_report(), AppLanguage.RU)
    dialog = InterpretationReportDetailsDialog(
        defaults,
        language=AppLanguage.RU,
        initial=_manual_identity(),
    )

    dialog.project_name.setText("Отредактированный проект")
    dialog.well_name.setText("Скважина-77")
    dialog.dataset_name.setText("Рабочий комплект ГТИ")
    selected = dialog.selected_identity()
    dialog.close()

    assert selected.project_name == "Отредактированный проект"
    assert selected.well_name == "Скважина-77"
    assert selected.dataset_name == "Рабочий комплект ГТИ"
    assert selected.document_number == "GAS-INT-012"
    assert selected.prepared_by == "Инженер ГТИ И.И."


def test_pdf_cover_uses_manual_identity_instead_of_loaded_file_names(qapp, tmp_path) -> None:
    target = tmp_path / "manual-cover.pdf"

    export_hydrocarbon_interpretation_pdf(
        _report(),
        target,
        language=AppLanguage.RU,
        include_chart=False,
        orientation=QPageLayout.Orientation.Portrait,
        identity=_manual_identity(),
    )

    with fitz.open(target) as document:
        cover_text = document[0].get_text()

    assert "Проект Северный купол" in cover_text
    assert "Северная-12" in cover_text
    assert "GAS-INT-012" in cover_text
    assert "АО Заказчик" in cover_text
    assert "ТОО Сервис ГТИ" in cover_text
    assert "Инженер ГТИ И.И." in cover_text
    assert "Техническое_имя_загруженного_файла.las" not in cover_text


def test_word_cover_is_separate_and_not_bunched_at_top(tmp_path) -> None:
    target = tmp_path / "manual-cover.docx"
    export_polished_hydrocarbon_interpretation_docx(
        _report(),
        target,
        identity=_manual_identity(),
    )

    with zipfile.ZipFile(target) as package:
        document_xml = package.read("word/document.xml")
    root = ET.fromstring(document_xml)
    body = root.find("w:body", _W)
    assert body is not None
    document_text = _word_text(root)

    assert "Отчёт ГТИ по скважине Северная-12" in document_text
    assert "Проект Северный купол" in document_text
    assert "GAS-INT-012" in document_text
    assert "АО Заказчик" in document_text
    assert "ТОО Сервис ГТИ" in document_text
    assert "Инженер ГТИ И.И." in document_text
    assert "Техническое_имя_загруженного_файла.las" not in document_text

    children = list(body)
    section_index = next(
        index
        for index, child in enumerate(children)
        if child.find("w:pPr/w:sectPr", _W) is not None
    )
    heading_index = next(
        index
        for index, child in enumerate(children)
        if "Методы и доступность" in _word_text(child)
    )
    assert section_index < heading_index

    sections = root.findall(".//w:sectPr", _W)
    assert len(sections) >= 2
    cover_type = sections[0].find("w:type", _W)
    cover_size = sections[0].find("w:pgSz", _W)
    body_size = sections[-1].find("w:pgSz", _W)
    assert cover_type is not None
    assert cover_type.get(f"{{{_W_NS}}}val") == "nextPage"
    assert cover_size is not None
    assert body_size is not None
    assert int(cover_size.get(f"{{{_W_NS}}}w", "0")) < int(
        cover_size.get(f"{{{_W_NS}}}h", "0")
    )
    assert body_size.get(f"{{{_W_NS}}}orient") == "landscape"
    assert int(body_size.get(f"{{{_W_NS}}}w", "0")) > int(
        body_size.get(f"{{{_W_NS}}}h", "0")
    )

    title_paragraph = next(
        paragraph
        for paragraph in body.findall("w:p", _W)
        if "Отчёт ГТИ по скважине Северная-12" in _word_text(paragraph)
    )
    title_spacing = title_paragraph.find("w:pPr/w:spacing", _W)
    assert title_spacing is not None
    assert int(title_spacing.get(f"{{{_W_NS}}}before", "0")) >= 720
    assert len(children[:section_index]) >= 8


@pytest.mark.parametrize(
    "orientation",
    (
        QPageLayout.Orientation.Portrait,
        QPageLayout.Orientation.Landscape,
    ),
)
def test_manual_cover_stays_inside_page_in_both_orientations(
    qapp,
    tmp_path,
    orientation: QPageLayout.Orientation,
) -> None:
    target = tmp_path / f"cover-{orientation.name}.pdf"
    export_hydrocarbon_interpretation_pdf(
        _report(),
        target,
        language=AppLanguage.RU,
        include_chart=False,
        orientation=orientation,
        identity=_manual_identity(),
    )

    with fitz.open(target) as document:
        page = document[0]
        assert (page.rect.width < page.rect.height) == (
            orientation is QPageLayout.Orientation.Portrait
        )
        safe_page = page.rect + (-1.5, -1.5, 1.5, 1.5)
        for block in page.get_text("dict")["blocks"]:
            for line in block.get("lines", ()):
                for span in line.get("spans", ()):
                    assert safe_page.contains(fitz.Rect(span["bbox"]))
        for drawing in page.get_drawings():
            assert safe_page.contains(fitz.Rect(drawing["rect"]))


def test_depth_scale_has_labelled_major_and_visible_minor_divisions() -> None:
    page = DepthPage(1_000.0, 1_200.0, 2_000, 330.0)

    major = major_depth_ticks(page, 330.0)
    minor = minor_depth_ticks(page)

    assert major[0] == 1_000.0
    assert major[-1] == 1_200.0
    assert len(major) >= 5
    assert len(minor) > len(major)
    assert all(
        all(abs(value - labelled) > 1e-6 for labelled in major)
        for value in minor
    )


def test_short_depth_interval_uses_more_frequent_numeric_labels() -> None:
    short_page = DepthPage(1_000.0, 1_010.0, 200, 140.0)
    long_page = DepthPage(1_000.0, 1_200.0, 2_000, 330.0)

    short_major = major_depth_ticks(short_page, 140.0)
    long_major = major_depth_ticks(long_page, 330.0)

    short_step = min(
        right - left
        for left, right in zip(short_major, short_major[1:], strict=False)
    )
    long_step = min(
        right - left
        for left, right in zip(long_major, long_major[1:], strict=False)
    )
    assert short_step < long_step
