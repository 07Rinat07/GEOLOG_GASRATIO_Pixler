from __future__ import annotations

import pytest
from PySide6.QtCore import Qt
from PySide6.QtPrintSupport import QPrinter
from PySide6.QtWidgets import QLabel

from geoworkbench.forms.a4_factory_templates import a4_factory_templates
from geoworkbench.printing.header_catalog import resolve_catalog_header
from geoworkbench.printing.page_settings import (
    PrintOrientation,
    PrintPageFormat,
    PrintPageSettings,
)
from geoworkbench.printing.print_job import PrintJobSettings, PrintOutputFormat
from geoworkbench.project.session import ProjectSession
from geoworkbench.services.localization import AppLanguage
from geoworkbench.services.print_jobs import PrintJobExecutor


_RICH_TEXT = {
    AppLanguage.RU: (
        "<p><b>Геологическое описание:</b> Песчаник мелкозернистый, "
        "с прослоями аргиллита и признаками углеводородов.</p>"
    ),
    AppLanguage.KK: (
        "<p><b>Геологиялық сипаттама:</b> Ұсақ түйірлі құмтас, "
        "аргиллит қабатшалары және көмірсутек белгілері бар.</p>"
    ),
    AppLanguage.EN: (
        "<p><b>Geological description:</b> Fine-grained sandstone with "
        "claystone interbeds and hydrocarbon indications.</p>"
    ),
}


@pytest.mark.parametrize("language", tuple(AppLanguage))
@pytest.mark.parametrize(
    "orientation",
    (PrintOrientation.PORTRAIT, PrintOrientation.LANDSCAPE),
)
def test_well05_preview_and_pdf_share_six_mode_form_header_configuration(
    qapp,
    tmp_path,
    language: AppLanguage,
    orientation: PrintOrientation,
) -> None:
    form = a4_factory_templates(language.value)[
        f"factory-technology-a4-{orientation.value}"
    ]
    header_id = form.print_header_for_orientation(orientation.value)
    assert header_id is not None
    header = resolve_catalog_header({}, header_id)

    assert form.preferred_page_orientation.value == orientation.value
    assert header.properties["preferred_orientation"] == orientation.value

    widget = QLabel(_RICH_TEXT[language])
    widget.setTextFormat(Qt.TextFormat.RichText)
    widget.setWordWrap(True)
    widget.resize(900, 620)
    widget.show()
    qapp.processEvents()

    page = PrintPageSettings(
        page_format=PrintPageFormat.A4,
        orientation=orientation,
    )
    executor = PrintJobExecutor()
    session = ProjectSession()

    preview_job = PrintJobSettings(
        output_format=PrintOutputFormat.PRINTER,
        page=page,
        dpi=96,
        header_template_id=header_id,
    )
    preview_path = tmp_path / f"preview-{language.value}-{orientation.value}.pdf"
    printer = executor.create_printer(widget, preview_job)
    printer.setOutputFormat(QPrinter.OutputFormat.PdfFormat)
    printer.setOutputFileName(str(preview_path))

    preview_pages = executor.render_preview(
        widget,
        printer,
        preview_job,
        source_name="WELL-05 six-mode preview",
        language=language,
        header_template=header,
        session=session,
    )

    target = tmp_path / f"output-{language.value}-{orientation.value}.pdf"
    pdf_job = PrintJobSettings(
        output_format=PrintOutputFormat.PDF,
        target=target,
        page=page,
        dpi=96,
        header_template_id=header_id,
    )
    result = executor.execute_file(
        widget,
        pdf_job,
        source_name="WELL-05 six-mode PDF",
        language=language,
        overwrite=True,
        header_template=header,
        session=session,
    )

    assert preview_pages >= 1
    assert result.page_count == preview_pages
    assert preview_path.read_bytes().startswith(b"%PDF")
    assert target.read_bytes().startswith(b"%PDF")
    assert preview_path.stat().st_size > 1_000
    assert target.stat().st_size > 1_000

    widget.close()
