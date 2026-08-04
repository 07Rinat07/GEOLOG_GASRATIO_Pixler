from __future__ import annotations

import os

import pytest
from PySide6.QtPdf import QPdfDocument
from PySide6.QtWidgets import QLabel

from geoworkbench.printing import document_export
from geoworkbench.printing.document_export import DocumentExportError
from geoworkbench.printing.document_renderer import PrintDocumentContext
from geoworkbench.printing.print_job import PrintJobSettings, PrintOutputFormat


class _SharingViolation(PermissionError):
    def __init__(self) -> None:
        super().__init__(13, "sharing violation")
        self.winerror = 32


def test_replace_pdf_file_retries_transient_sharing_violation(
    tmp_path, monkeypatch
) -> None:
    temporary = tmp_path / ".report.pdf.tmp"
    destination = tmp_path / "report.pdf"
    temporary.write_bytes(b"%PDF-1.4\n")
    real_replace = os.replace
    attempts = 0

    def flaky_replace(source, target) -> None:
        nonlocal attempts
        attempts += 1
        if attempts < 3:
            raise _SharingViolation()
        real_replace(source, target)

    monkeypatch.setattr(document_export.os, "replace", flaky_replace)
    monkeypatch.setattr(document_export.time, "sleep", lambda _seconds: None)

    document_export._replace_pdf_file(temporary, destination)

    assert attempts == 3
    assert destination.read_bytes().startswith(b"%PDF-1.4")
    assert not temporary.exists()


def test_replace_pdf_file_does_not_retry_unrelated_error(
    tmp_path, monkeypatch
) -> None:
    temporary = tmp_path / ".report.pdf.tmp"
    destination = tmp_path / "report.pdf"
    temporary.write_bytes(b"%PDF-1.4\n")
    attempts = 0

    def failing_replace(_source, _target) -> None:
        nonlocal attempts
        attempts += 1
        raise OSError("disk failure")

    monkeypatch.setattr(document_export.os, "replace", failing_replace)

    with pytest.raises(OSError, match="disk failure"):
        document_export._replace_pdf_file(temporary, destination)
    assert attempts == 1


def test_pdf_export_error_includes_underlying_reason(
    tmp_path, monkeypatch
) -> None:
    target = tmp_path / "report.pdf"
    temporary = tmp_path / ".report.pdf.tmp"
    temporary.write_bytes(b"")
    monkeypatch.setattr(document_export, "_detached_tablet_source", lambda _w: None)
    monkeypatch.setattr(document_export, "_validate_destination", lambda *_a: None)
    monkeypatch.setattr(document_export, "_unicode_preflight", lambda *_a: None)
    monkeypatch.setattr(document_export, "_temporary_path", lambda _p: temporary)

    def fail_render(*_args, **_kwargs):
        raise OSError("renderer exploded")

    monkeypatch.setattr(document_export, "_render_document_pdf_file", fail_render)
    job = PrintJobSettings(output_format=PrintOutputFormat.PDF, target=target)

    with pytest.raises(DocumentExportError, match="renderer exploded"):
        document_export.export_document_pdf(
            object(),
            target,
            job,
            context=PrintDocumentContext("Diagnostics"),
        )


def test_repeated_real_pdf_exports_leave_no_temporary_files(
    qapp, tmp_path
) -> None:
    widget = QLabel("LAS / GeoScape II PDF export")
    widget.resize(500, 240)
    widget.show()
    qapp.processEvents()

    for index in range(3):
        target = tmp_path / f"report-{index}.pdf"
        job = PrintJobSettings(
            output_format=PrintOutputFormat.PDF,
            target=target,
            dpi=96,
        )
        document_export.export_document_pdf(
            widget,
            target,
            job,
            context=PrintDocumentContext("Repeated PDF export"),
        )
        document = QPdfDocument()
        assert document.load(str(target)) == QPdfDocument.Error.None_
        assert document.pageCount() == 1

    assert not tuple(tmp_path.glob(".*.tmp"))
    widget.close()
