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
from geoworkbench.printing.hydrocarbon_interpretation_report_range import (
    ReportDepthRange,
    scope_report_to_depth_range,
)
from geoworkbench.printing.report_visual_system import REPORT_BRAND_WORDMARK
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


LEGACY_PRODUCT_NAME = "GEOLOG GASRATIO" + "@" + "Pixler"

def test_report_scoping_preserves_generation_audit_timestamp() -> None:
    report = _report()

    scoped = scope_report_to_depth_range(
        report,
        ReportDepthRange(1000.0, 1200.0),
    )

    assert scoped.generated_at == report.generated_at
    assert scoped.generated_at == "2026-08-01T11:30:00+05:00"


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
    assert identity.report_date == ""


def test_default_pdf_cover_hides_generation_timestamp(qapp, tmp_path) -> None:
    target = tmp_path / "default-cover-no-generated-time.pdf"

    export_hydrocarbon_interpretation_pdf(
        _report(),
        target,
        language=AppLanguage.RU,
        include_chart=False,
        orientation=QPageLayout.Orientation.Portrait,
    )

    with fitz.open(target) as document:
        cover_text = document[0].get_text()

    assert "Дата отчёта" not in cover_text
    assert "Порог robust z" in cover_text
    assert "Сформирован" not in cover_text
    assert "2026-08-01T11:30:00+05:00" not in cover_text
    assert "11:30" not in cover_text


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
    assert "Дата отчёта" in cover_text
    assert "01.08.2026" in cover_text
    assert "2026-08-01T11:30:00+05:00" not in cover_text
    assert "Сформирован" not in cover_text
    assert REPORT_BRAND_WORDMARK in cover_text
    assert LEGACY_PRODUCT_NAME not in cover_text
    assert "Техническое_имя_загруженного_файла.las" not in cover_text


def test_default_word_cover_uses_full_width_three_column_control_table(tmp_path) -> None:
    target = tmp_path / "default-cover.docx"
    export_polished_hydrocarbon_interpretation_docx(_report(), target)

    with zipfile.ZipFile(target) as package:
        root = ET.fromstring(package.read("word/document.xml"))

    document_text = _word_text(root)
    assert "Дата отчёта" not in document_text
    assert "Сформирован" not in document_text

    control_table = root.find(".//w:tbl", _W)
    assert control_table is not None
    table_width = control_table.find("w:tblPr/w:tblW", _W)
    assert table_width is not None
    assert table_width.get(f"{{{_W_NS}}}w") == "9000"
    grid_widths = [
        int(column.get(f"{{{_W_NS}}}w", "0"))
        for column in control_table.findall("w:tblGrid/w:gridCol", _W)
    ]
    assert grid_widths == [3000, 3000, 3000]


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
    assert "Дата отчёта" in document_text
    assert "01.08.2026" in document_text
    assert "2026-08-01T11:30:00+05:00" not in document_text
    assert "Сформирован" not in document_text
    assert REPORT_BRAND_WORDMARK in document_text
    assert LEGACY_PRODUCT_NAME not in document_text
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


def test_pdf_body_uses_edited_passport_instead_of_stale_las_headings(qapp, tmp_path) -> None:
    report = _report()
    details = _manual_identity()
    destination = tmp_path / "consistent-passport.pdf"
    export_hydrocarbon_interpretation_pdf(
        report, destination, identity=details, language=AppLanguage.RU,
    )
    with fitz.open(destination) as document:
        assert document.page_count >= 2
        full_text = "\n".join(page.get_text() for page in document)

    for text in (
        details.project_name, details.well_name, details.dataset_name,
    ):
        assert text in full_text
    for obsolete in (
        report.project_name, report.well_name, report.dataset_name,
    ):
        assert obsolete not in full_text
    assert report.well_name == "Файл-скважина-494"  # source is unchanged


def test_html_preview_uses_edited_passport_without_changing_detection(monkeypatch) -> None:
    from geoworkbench.printing import hydrocarbon_interpretation_chart_front as front
    from geoworkbench.printing.hydrocarbon_interpretation_report_identity import (
        report_with_presentation_identity,
    )
    from geoworkbench.services.hydrocarbon_interpretation import (
        build_hydrocarbon_interpretation_report,
    )
    from test_interpretation_report_charts import _session_with_report_curves

    session = _session_with_report_curves(depth_span=30, samples=61)
    dataset = session.current_dataset
    assert dataset is not None
    report = build_hydrocarbon_interpretation_report(session)
    edited = _manual_identity()
    monkeypatch.setattr(front, "hydrocarbon_interpretation_chart_data_uri", lambda *args, **kw: None)
    html = front.hydrocarbon_interpretation_html_with_front_chart(
        report, dataset, language=AppLanguage.RU, identity=edited,
    )
    assert edited.project_name in html
    assert edited.well_name in html
    assert edited.dataset_name in html
    for name in (report.project_name, report.well_name, report.dataset_name):
        if name and name not in (edited.project_name, edited.well_name, edited.dataset_name):
            assert name not in html

    rendered = report_with_presentation_identity(report, edited)
    assert rendered.well_name == edited.well_name
    assert rendered.candidates is report.candidates
    assert rendered.methods is report.methods
    assert report_with_presentation_identity(report, None) is report
    assert report.well_name != edited.well_name
