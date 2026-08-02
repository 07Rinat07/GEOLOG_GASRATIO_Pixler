from __future__ import annotations

from pathlib import Path

from PySide6.QtWidgets import QLabel

from geoworkbench.printing.document_export import PrintDocumentResult
from geoworkbench.printing.pagination import PrintPaginationSettings
from geoworkbench.printing.print_job import PrintJobSettings, PrintOutputFormat
from geoworkbench.services.localization import AppLanguage
from geoworkbench.services.print_jobs import PrintJobExecutor, report_render_settings


def test_available_printers_are_default_first(monkeypatch) -> None:
    class FakePrinterInfo:
        def __init__(self, name: str, default: bool) -> None:
            self._name = name
            self._default = default

        def printerName(self) -> str:
            return self._name

        def isDefault(self) -> bool:
            return self._default

    class FakePrinterCatalog:
        @staticmethod
        def availablePrinters():
            return [
                FakePrinterInfo("Office Printer", False),
                FakePrinterInfo("Engineering Plotter", True),
            ]

    monkeypatch.setattr(
        "geoworkbench.services.print_jobs.QPrinterInfo", FakePrinterCatalog
    )

    assert PrintJobExecutor().available_printers() == (
        ("Engineering Plotter", True),
        ("Office Printer", False),
    )


def test_file_executor_routes_pdf_and_normalizes_target(monkeypatch, qapp, tmp_path) -> None:
    widget = QLabel("Print job")
    widget.resize(640, 360)
    captured: dict[str, object] = {}

    def fake_export(widget_arg, target, job, *, context, overwrite=False):
        captured.update(
            widget=widget_arg,
            target=target,
            job=job,
            title=context.title,
            overwrite=overwrite,
        )
        return PrintDocumentResult((Path(target),), 3)

    monkeypatch.setattr("geoworkbench.services.print_jobs.export_document_pdf", fake_export)
    job = PrintJobSettings(
        output_format=PrintOutputFormat.PDF,
        target=tmp_path / "report.txt",
        dpi=96,
    )

    result = PrintJobExecutor().execute_file(
        widget,
        job,
        source_name="Gas Ratio",
        language=AppLanguage.EN,
        overwrite=True,
    )

    assert captured["widget"] is widget
    assert captured["target"] == tmp_path / "report.pdf"
    assert captured["overwrite"] is True
    assert "Gas Ratio" in str(captured["title"])
    assert result.output_format is PrintOutputFormat.PDF
    assert result.page_count == 3
    assert result.primary_path == tmp_path / "report.pdf"


def test_file_executor_routes_page_formats(monkeypatch, qapp, tmp_path) -> None:
    widget = QLabel("Pages")
    produced = (tmp_path / "page_001.png", tmp_path / "page_002.png")

    def fake_export(widget_arg, target, job, *, context, overwrite=False):
        assert widget_arg is widget
        assert target == tmp_path / "page.png"
        assert job.output_format is PrintOutputFormat.PNG
        assert context.title
        assert overwrite is False
        return PrintDocumentResult(produced, 2)

    monkeypatch.setattr("geoworkbench.services.print_jobs.export_document_pages", fake_export)
    job = PrintJobSettings(
        output_format=PrintOutputFormat.PNG,
        target=tmp_path / "page.png",
        dpi=96,
    )

    result = PrintJobExecutor().execute_file(
        widget,
        job,
        source_name="Tablet",
        language=AppLanguage.RU,
    )

    assert result.paths == produced
    assert result.page_count == 2


def test_printer_executor_uses_supplied_printer(monkeypatch, qapp, tmp_path) -> None:
    widget = QLabel("Printer")
    job = PrintJobSettings(
        output_format=PrintOutputFormat.PRINTER,
        dpi=96,
        copy_count=3,
    )
    executor = PrintJobExecutor()
    printer = executor.create_printer(widget, job)
    assert printer.copyCount() == 3
    captured: dict[str, object] = {}

    def fake_render(widget_arg, printer_arg, job_arg, *, context):
        captured.update(widget=widget_arg, printer=printer_arg, job=job_arg, title=context.title)
        return 4

    monkeypatch.setattr("geoworkbench.services.print_jobs.render_document_to_printer", fake_render)

    print_copy = tmp_path / "Curves_print_copy.pdf"

    def fake_export(widget_arg, target, job_arg, *, context, overwrite=False):
        assert widget_arg is widget
        assert target == print_copy
        assert job_arg.output_format is PrintOutputFormat.PDF
        assert context.title
        assert overwrite is False
        print_copy.write_bytes(b"%PDF-1.7\n")
        return PrintDocumentResult((print_copy,), 4)

    monkeypatch.setattr(
        "geoworkbench.services.print_jobs._physical_print_copy_path",
        lambda _source_name: print_copy,
    )
    monkeypatch.setattr(
        "geoworkbench.services.print_jobs.export_document_pdf",
        fake_export,
    )

    result = executor.render_to_printer(
        widget,
        printer,
        job,
        source_name="Curves",
        language=AppLanguage.KK,
    )

    assert captured["widget"] is widget
    assert captured["printer"] is printer
    assert result.output_format is PrintOutputFormat.PRINTER
    assert result.page_count == 4
    assert result.paths == (print_copy,)
    assert result.primary_path == print_copy


def test_report_render_settings_preserve_tablet_print_composition(tmp_path) -> None:
    import json

    job = PrintJobSettings(
        output_format=PrintOutputFormat.PDF,
        target=tmp_path / "tablet.pdf",
        included_track_ids=("depth", "gas"),
        grid_print_overrides=(("depth", True), ("gas", False)),
        pagination=PrintPaginationSettings(auto_units_per_page=True),
    )

    options = dict(report_render_settings(job).options)

    assert json.loads(options["included_track_ids"]) == ["depth", "gas"]
    assert json.loads(options["grid_print_overrides"]) == [
        ["depth", True],
        ["gas", False],
    ]
    assert options["auto_units_per_page"] == "true"
