from __future__ import annotations

from collections.abc import Iterable

import fitz

from geoworkbench.files.document_service import DocumentError, DocumentService


class EnhancedDocumentService(DocumentService):
    """Document service extensions used by the interactive PDF tools."""

    def erase_pdf_rects(
        self,
        rects: Iterable[tuple[float, float, float, float]],
    ) -> int:
        page = self._pdf_page()
        page_rect = page.rect
        prepared: list[fitz.Rect] = []
        for raw in rects:
            rect = fitz.Rect(*raw) & page_rect
            if rect.width >= 0.5 and rect.height >= 0.5:
                prepared.append(rect)
        if not prepared:
            raise DocumentError("Не удалось определить траекторию ластика")
        if len(prepared) > 2500:
            raise DocumentError("Траектория ластика слишком длинная")

        self._begin_edit()
        try:
            for rect in prepared:
                page.add_redact_annot(rect, fill=(1.0, 1.0, 1.0), cross_out=False)
            page.apply_redactions(images=fitz.PDF_REDACT_IMAGE_PIXELS)
        except Exception as exc:
            self.undo()
            raise DocumentError(f"Не удалось применить ластик: {exc}") from exc
        self.dirty = True
        return len(prepared)

    def add_styled_pdf_text(
        self,
        rect: tuple[float, float, float, float],
        text: str,
        *,
        fontname: str,
        font_size: float,
        color: tuple[float, float, float],
        alignment: int,
        background: tuple[float, float, float] | None = None,
        replace: bool = False,
    ) -> None:
        page = self._pdf_page()
        if not text.strip():
            raise DocumentError("Введите текст")
        target = fitz.Rect(*rect) & page.rect
        if target.width < 4 or target.height < 4:
            raise DocumentError("Выделенная область слишком мала")

        self._begin_edit()
        try:
            if replace:
                page.add_redact_annot(target, fill=(1.0, 1.0, 1.0), cross_out=False)
                page.apply_redactions(images=fitz.PDF_REDACT_IMAGE_PIXELS)
            if background is not None:
                page.draw_rect(target, color=None, fill=background, overlay=True)
            remaining = page.insert_textbox(
                target,
                text,
                fontsize=max(4.0, min(144.0, font_size)),
                color=color,
                fontname=fontname,
                align=max(0, min(2, alignment)),
                overlay=True,
            )
            if remaining < 0:
                raise DocumentError(
                    "Текст не помещается: увеличьте область или уменьшите размер шрифта"
                )
        except Exception as exc:
            self.undo()
            if isinstance(exc, DocumentError):
                raise
            raise DocumentError(f"Не удалось вставить текст: {exc}") from exc
        self.dirty = True
