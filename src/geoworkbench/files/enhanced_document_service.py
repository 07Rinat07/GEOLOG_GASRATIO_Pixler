from __future__ import annotations

from collections.abc import Iterable
import html

import fitz

from geoworkbench.files.document_service import DocumentError, DocumentService, _Snapshot


_FONT_FAMILIES: dict[str, str] = {
    "helv": "sans-serif",
    "hebo": "sans-serif",
    "heit": "sans-serif",
    "hebi": "sans-serif",
    "tiro": "serif",
    "tibo": "serif",
    "tiit": "serif",
    "tibi": "serif",
    "cour": "monospace",
    "cobo": "monospace",
    "coit": "monospace",
    "cobi": "monospace",
}

_BOLD_FONTS = {"hebo", "hebi", "tibo", "tibi", "cobo", "cobi"}
_ITALIC_FONTS = {"heit", "hebi", "tiit", "tibi", "coit", "cobi"}


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
    def _insert_html_text(
        page: fitz.Page,
        target: fitz.Rect,
        text: str,
        *,
        fontname: str,
        font_size: float,
        color: tuple[float, float, float],
        alignment: int,
    ) -> float:
        family = _FONT_FAMILIES.get(fontname)
        if family is None:
            raise DocumentError(f"Неподдерживаемый PDF-шрифт: {fontname}")
        red, green, blue = (
            round(max(0.0, min(1.0, component)) * 255) for component in color
        )
        align = ("left", "center", "right")[max(0, min(2, alignment))]
        weight = "bold" if fontname in _BOLD_FONTS else "normal"
        style = "italic" if fontname in _ITALIC_FONTS else "normal"
        size = max(4.0, min(144.0, font_size))
        css = (
            f"* {{ font-family: {family}; font-size: {size:.3f}pt; "
            f"font-weight: {weight}; font-style: {style}; "
            f"color: rgb({red}, {green}, {blue}); text-align: {align}; "
            "white-space: pre-wrap; }}"
        )
        payload = html.escape(text).replace("\n", "<br>")
        remaining, _scale = page.insert_htmlbox(
            target,
            f"<div>{payload}</div>",
            css=css,
            scale_low=1,
            overlay=True,
        )
        return float(remaining)

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
            if replace:
                page.add_redact_annot(target, fill=(1.0, 1.0, 1.0), cross_out=False)
                page.apply_redactions(images=fitz.PDF_REDACT_IMAGE_PIXELS)
            if background is not None:
                page.draw_rect(target, color=None, fill=background, overlay=True)
            remaining = self._insert_html_text(
                page,
                target,
                text,
                fontname=fontname,
                font_size=font_size,
                color=color,
                alignment=alignment,
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
