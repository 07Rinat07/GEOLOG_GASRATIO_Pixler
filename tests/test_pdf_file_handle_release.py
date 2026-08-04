from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

from PySide6.QtWidgets import QLabel

from geoworkbench.printing import document_export
from geoworkbench.printing.document_renderer import PrintDocumentContext
from geoworkbench.printing.print_job import PrintJobSettings, PrintOutputFormat


def test_pdf_writer_is_released_before_atomic_replace(
    qapp, tmp_path, monkeypatch
) -> None:
    _ = qapp

    class FakePdfWriter:
        open_paths: set[Path] = set()

        def __init__(self, path: str) -> None:
            self.path = Path(path)
            self.stream = self.path.open("wb")
            self.stream.write(b"%PDF-1.4\n")
            self.stream.flush()
            type(self).open_paths.add(self.path)

        def __del__(self) -> None:
            self.stream.close()
            type(self).open_paths.discard(self.path)

        def setPageSize(self, _page_size) -> None:
            pass

        def setPageOrientation(self, _orientation) -> None:
            pass

        def setPageMargins(self, _margins, _unit) -> None:
            pass

        def setResolution(self, _dpi: int) -> None:
            pass

        def setTitle(self, _title: str) -> None:
            pass

        def setCreator(self, _creator: str) -> None:
            pass

        def width(self) -> int:
            return 100

        def height(self) -> int:
            return 100

    class FakePainter:
        def __init__(self) -> None:
            self.active = False

        def begin(self, _device) -> bool:
            self.active = True
            return True

        def end(self) -> bool:
            self.active = False
            return True

        def isActive(self) -> bool:
            return self.active

    original_replace = document_export.os.replace

    def guarded_replace(source, destination) -> None:
        assert Path(source) not in FakePdfWriter.open_paths
        original_replace(source, destination)

    monkeypatch.setattr(document_export, "QPdfWriter", FakePdfWriter)
    monkeypatch.setattr(document_export, "QPainter", FakePainter)
    monkeypatch.setattr(
        document_export,
        "printable_content_dimensions",
        lambda _widget, _job: (100, 100),
    )
    monkeypatch.setattr(
        document_export,
        "paint_document_pages",
        lambda *_args, **_kwargs: SimpleNamespace(page_count=1),
    )
    monkeypatch.setattr(
        document_export,
        "_unicode_preflight",
        lambda *_args: None,
    )
    monkeypatch.setattr(document_export.os, "replace", guarded_replace)

    widget = QLabel("PDF handle regression")
    target = tmp_path / "Планшет.pdf"
    job = PrintJobSettings(
        output_format=PrintOutputFormat.PDF,
        target=target,
        dpi=96,
    )

    result = document_export.export_document_pdf(
        widget,
        target,
        job,
        context=PrintDocumentContext("Планшет"),
    )

    assert result.paths == (target,)
    assert target.read_bytes().startswith(b"%PDF-1.4")
    assert not FakePdfWriter.open_paths
    widget.close()
