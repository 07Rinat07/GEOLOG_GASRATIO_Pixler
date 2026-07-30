from __future__ import annotations

from collections.abc import Iterable

import fitz

from geoworkbench.files.document_service import DocumentError, DocumentService, _Snapshot


_FONT_ALIASES: dict[str, str] = {
    "helv": "GWHelveticaRegular",
    "hebo": "GWHelveticaBold",
    "heit": "GWHelveticaItalic",
    "hebi": "GWHelveticaBoldItalic",
    "tiro": "GWTimesRegular",
    "tibo": "GWTimesBold",
    "tiit": "GWTimesItalic",
    "tibi": "GWTimesBoldItalic",
    "cour": "GWCourierRegular",
    "cobo": "GWCourierBold",
    "coit": "GWCourierItalic",
    "cobi": "GWCourierBoldItalic",
}


class EnhancedDocumentService(DocumentService):
    """Document service extensions used by the interactive PDF tools."""

    def erase_pdf_rects(
        self,
        rects: Iterable[tuple[float, float, float, float]],
    ) -> int:
        """Erase rectangles already expressed in the unrotated PDF page space."""
        return self._erase_pdf_rects(self._pdf_page(), rects)

    def erase_pdf_display_rects(
        self,
        rects: Iterable[tuple[float, float, float, float]],
    ) -> int:
        """Erase rectangles expressed in the visible, possibly rotated page space."""
        page = self._pdf_page()
        matrix = page.derotation_matrix
        transformed = (fitz.Rect(*raw) * matrix for raw in rects)
        return self._erase_pdf_rects(
            page,
            ((rect.x0, rect.y0, rect.x1, rect.y1) for rect in transformed),
        )

    def _erase_pdf_rects(
        self,
        page: fitz.Page,
        rects: Iterable[tuple[float, float, float, float]],
    ) -> int:
        page_bounds = page.cropbox
        prepared: list[fitz.Rect] = []
        for raw in rects:
            rect = fitz.Rect(*raw) & page_bounds
            if rect.width >= 0.5 and rect.height >= 0.5:
                prepared.append(rect)
        if not prepared:
            raise DocumentError("Не удалось определить траекторию ластика")
        if len(prepared) > 2500:
            raise DocumentError("Траектория ластика слишком длинная")

        before, dirty_before, undo_before, redo_before = self._transaction_state()
        try:
            for rect in prepared:
                page.add_redact_annot(rect, fill=(1.0, 1.0, 1.0), cross_out=False)
            page.apply_redactions(images=fitz.PDF_REDACT_IMAGE_PIXELS)
        except Exception as exc:
            self._rollback_transaction(before, dirty_before, undo_before, redo_before)
            raise DocumentError(f"Не удалось применить ластик: {exc}") from exc
        self._commit_transaction(before)
        return len(prepared)

    @staticmethod
    def _install_unicode_font(page: fitz.Page, fontname: str) -> str:
        alias = _FONT_ALIASES.get(fontname)
        if alias is None:
            raise DocumentError(f"Неподдерживаемый PDF-шрифт: {fontname}")
        try:
            font = fitz.Font(fontname)
            page.insert_font(fontname=alias, fontbuffer=font.buffer)
        except Exception as exc:
            raise DocumentError(f"Не удалось встроить PDF-шрифт: {exc}") from exc
        return alias

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
        target = fitz.Rect(*rect) & page.cropbox
        if target.width < 4 or target.height < 4:
            raise DocumentError("Выделенная область слишком мала")

        before, dirty_before, undo_before, redo_before = self._transaction_state()
        try:
            embedded_font = self._install_unicode_font(page, fontname)
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
                fontname=embedded_font,
                align=max(0, min(2, alignment)),
                overlay=True,
            )
            if remaining < 0:
                raise DocumentError(
                    "Текст не помещается: увеличьте область или уменьшите размер шрифта"
                )
        except Exception as exc:
            self._rollback_transaction(before, dirty_before, undo_before, redo_before)
            if isinstance(exc, DocumentError):
                raise
            raise DocumentError(f"Не удалось вставить текст: {exc}") from exc
        self._commit_transaction(before)

    def _transaction_state(
        self,
    ) -> tuple[_Snapshot, bool, list[_Snapshot], list[_Snapshot]]:
        return self._snapshot(), self.dirty, list(self._undo), list(self._redo)

    def _commit_transaction(self, before: _Snapshot) -> None:
        self._undo.append(before)
        if len(self._undo) > 20:
            del self._undo[0]
        self._redo.clear()
        self.dirty = True

    def _rollback_transaction(
        self,
        before: _Snapshot,
        dirty_before: bool,
        undo_before: list[_Snapshot],
        redo_before: list[_Snapshot],
    ) -> None:
        self._restore(before)
        self.dirty = dirty_before
        self._undo[:] = undo_before
        self._redo[:] = redo_before
