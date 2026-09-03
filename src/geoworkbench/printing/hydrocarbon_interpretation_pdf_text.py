from __future__ import annotations

from dataclasses import dataclass
import re

from PySide6.QtCore import QRectF
from PySide6.QtGui import QTextDocument

from geoworkbench.printing.hydrocarbon_interpretation_pdf_canvas import PageCanvas
from geoworkbench.printing.unicode_support import print_font


_VOID_TAGS = frozenset(
    {
        "area",
        "base",
        "br",
        "col",
        "embed",
        "hr",
        "img",
        "input",
        "link",
        "meta",
        "param",
        "source",
        "track",
        "wbr",
    }
)
_TAG_PATTERN = re.compile(
    r"<!--.*?-->|<![^>]*>|<\s*(/?)\s*([A-Za-z0-9]+)\b[^>]*>",
    re.S,
)
_STYLE_PATTERN = re.compile(r"<style\b[^>]*>(.*?)</style>", re.I | re.S)
_BODY_PATTERN = re.compile(r"<body\b[^>]*>(.*?)</body>", re.I | re.S)
_ROW_PATTERN = re.compile(r"<tr\b[^>]*>.*?</tr>", re.I | re.S)
_THEAD_PATTERN = re.compile(r"<thead\b[^>]*>.*?</thead>", re.I | re.S)
_TBODY_PATTERN = re.compile(r"<tbody\b[^>]*>(.*?)</tbody>", re.I | re.S)
_COLGROUP_PATTERN = re.compile(r"<colgroup\b[^>]*>.*?</colgroup>", re.I | re.S)
_LIST_ITEM_PATTERN = re.compile(r"<li\b[^>]*>.*?</li>", re.I | re.S)


@dataclass(frozen=True, slots=True)
class _TableParts:
    opening: str
    colgroup: str
    thead: str
    rows: tuple[str, ...]


def render_report_html(
    canvas: PageCanvas,
    html: str,
    *,
    leading_block_count: int = 2,
    after_leading_blocks: object | None = None,
) -> None:
    """Render top-level report blocks with controlled table-row pagination."""

    style = _document_style(html)
    blocks = _top_level_body_blocks(html)
    split_index = min(max(0, leading_block_count), len(blocks))
    for block in blocks[:split_index]:
        _render_atomic_html(canvas, style, block)

    if callable(after_leading_blocks):
        after_leading_blocks()

    if split_index < len(blocks):
        if canvas.has_content:
            canvas.new_page()
        _render_html_blocks(canvas, style, blocks[split_index:])


def _render_html_blocks(
    canvas: PageCanvas,
    style: str,
    blocks: tuple[str, ...],
) -> None:
    index = 0
    while index < len(blocks):
        block = blocks[index]
        next_block = blocks[index + 1] if index + 1 < len(blocks) else ""
        if _is_heading(block) and next_block.lstrip().lower().startswith("<table"):
            _render_table(canvas, style, next_block, heading=block)
            index += 2
            continue
        if _is_heading(block) and _is_notice(next_block):
            _render_notice(canvas, style, next_block, heading=block)
            index += 2
            continue
        if block.lstrip().lower().startswith("<table"):
            _render_table(canvas, style, block)
        elif _is_notice(block):
            _render_notice(canvas, style, block)
        elif _is_heading(block) and next_block:
            _render_atomic_html(canvas, style, block + next_block)
            index += 1
        else:
            _render_atomic_html(canvas, style, block)
        index += 1


def _render_table(
    canvas: PageCanvas,
    style: str,
    table_html: str,
    *,
    heading: str = "",
) -> None:
    parts = _table_parts(table_html)
    if not parts.rows:
        _render_atomic_html(canvas, style, heading + table_html, table=True)
        return

    row_index = 0
    first_chunk = True
    while row_index < len(parts.rows):
        prefix = heading if first_chunk else ""
        available = canvas.remaining_height
        if available < 80.0 and canvas.has_content:
            canvas.new_page()
            available = canvas.remaining_height
        best_end = row_index
        best_html = ""
        best_height = 0.0
        end = row_index + 1
        while end <= len(parts.rows):
            candidate = prefix + _table_html(parts, parts.rows[row_index:end])
            _document, height = _html_document(
                style,
                candidate,
                canvas.content_rect.width(),
                table=True,
            )
            if height <= available + 0.5:
                best_end = end
                best_html = candidate
                best_height = height
                end += 1
                continue
            break
        if best_end == row_index:
            if canvas.has_content:
                canvas.new_page()
                continue
            candidate = prefix + _table_html(parts, (parts.rows[row_index],))
            compact_document, compact_height = _html_document(
                style,
                candidate,
                canvas.content_rect.width(),
                table=True,
                compact_table=True,
            )
            if compact_height <= canvas.remaining_height + 0.5:
                _draw_document(canvas, compact_document, compact_height)
            else:
                _render_atomic_html(
                    canvas,
                    style,
                    candidate,
                    table=True,
                    allow_scale=True,
                    compact_table=True,
                )
            row_index += 1
            first_chunk = False
            continue
        _draw_html(canvas, style, best_html, best_height, table=True)
        row_index = best_end
        first_chunk = False
        if row_index < len(parts.rows):
            canvas.new_page()


def _render_notice(
    canvas: PageCanvas,
    style: str,
    notice_html: str,
    *,
    heading: str = "",
) -> None:
    items = tuple(_LIST_ITEM_PATTERN.findall(notice_html))
    if not items:
        _render_atomic_html(canvas, style, heading + notice_html)
        return
    open_match = re.match(r"\s*(<div\b[^>]*>)", notice_html, re.I | re.S)
    opening = open_match.group(1) if open_match else "<div class='notice'>"
    inner_heading = "".join(
        re.findall(r"<h2\b[^>]*>.*?</h2>", notice_html, re.I | re.S)
    )
    item_index = 0
    first_chunk = True
    while item_index < len(items):
        prefix = heading if first_chunk else ""
        available = canvas.remaining_height
        if available < 70.0 and canvas.has_content:
            canvas.new_page()
            available = canvas.remaining_height
        best_end = item_index
        best_html = ""
        best_height = 0.0
        end = item_index + 1
        while end <= len(items):
            candidate = (
                prefix
                + opening
                + inner_heading
                + "<ul>"
                + "".join(items[item_index:end])
                + "</ul></div>"
            )
            _document, height = _html_document(
                style,
                candidate,
                canvas.content_rect.width(),
            )
            if height <= available + 0.5:
                best_end = end
                best_html = candidate
                best_height = height
                end += 1
                continue
            break
        if best_end == item_index:
            if canvas.has_content:
                canvas.new_page()
                continue
            candidate = (
                prefix
                + opening
                + inner_heading
                + "<ul>"
                + items[item_index]
                + "</ul></div>"
            )
            _render_atomic_html(canvas, style, candidate, allow_scale=True)
            item_index += 1
            first_chunk = False
            continue
        _draw_html(canvas, style, best_html, best_height)
        item_index = best_end
        first_chunk = False
        if item_index < len(items):
            canvas.new_page()


def _render_atomic_html(
    canvas: PageCanvas,
    style: str,
    fragment: str,
    *,
    table: bool = False,
    allow_scale: bool = False,
    compact_table: bool = False,
) -> None:
    document, height = _html_document(
        style,
        fragment,
        canvas.content_rect.width(),
        table=table,
        compact_table=compact_table,
    )
    canvas.reserve(height)
    if height <= canvas.remaining_height + 0.5:
        _draw_document(canvas, document, height)
        return
    if canvas.has_content:
        canvas.new_page()
    if height <= canvas.remaining_height + 0.5:
        _draw_document(canvas, document, height)
        return

    # ``allow_scale`` is kept for compatibility with the row/list fallback
    # callers. Oversized fragments keep the physical A4 width; only an
    # exceptional oversized table row may use the compact table typography
    # selected above before it is vertically paginated.
    _ = allow_scale
    _draw_document_paginated(canvas, document, height)


def _draw_html(
    canvas: PageCanvas,
    style: str,
    fragment: str,
    height: float,
    *,
    table: bool = False,
) -> None:
    document, measured = _html_document(
        style,
        fragment,
        canvas.content_rect.width(),
        table=table,
    )
    _draw_document(canvas, document, max(height, measured))


def _draw_document(
    canvas: PageCanvas,
    document: QTextDocument,
    height: float,
) -> None:
    painter = canvas.painter
    painter.save()
    try:
        painter.translate(canvas.content_rect.left(), canvas.y)
        document.drawContents(
            painter,
            QRectF(
                0.0,
                0.0,
                canvas.content_rect.width(),
                height,
            ),
        )
    finally:
        painter.restore()
    canvas.advance(height)


def _draw_document_paginated(
    canvas: PageCanvas,
    document: QTextDocument,
    height: float,
) -> None:
    """Draw a tall document at full width without leaving tiny tail pages."""

    offset = 0.0
    epsilon = 0.5
    page_capacity = max(1.0, float(canvas.content_rect.height()))
    minimum_final_slice = min(
        page_capacity * 0.30,
        max(24.0, page_capacity * 0.20),
    )
    while offset < height - epsilon:
        if canvas.remaining_height <= epsilon:
            canvas.new_page()
            continue

        available = canvas.remaining_height
        remaining = height - offset
        slice_height = min(available, remaining)
        if remaining > available + epsilon:
            tail_height = remaining - available
            if 0.0 < tail_height < minimum_final_slice:
                borrow = min(
                    minimum_final_slice - tail_height,
                    available * 0.35,
                )
                slice_height = max(available * 0.55, available - borrow)

        painter = canvas.painter
        painter.save()
        try:
            painter.translate(
                canvas.content_rect.left(),
                canvas.y - offset,
            )
            document.drawContents(
                painter,
                QRectF(
                    0.0,
                    offset,
                    canvas.content_rect.width(),
                    slice_height,
                ),
            )
        finally:
            painter.restore()

        offset += slice_height
        canvas.advance(slice_height, spacing=0.0)
        if offset < height - epsilon:
            canvas.new_page()

    canvas.advance(0.0, spacing=5.0)


def _html_document(
    style: str,
    fragment: str,
    width: float,
    *,
    table: bool = False,
    compact_table: bool = False,
) -> tuple[QTextDocument, float]:
    overrides = """
html, body { background: #ffffff; color: #172033; }
body { margin: 0; font-size: 9pt; }
h1 { margin: 0 0 8px 0; font-size: 17pt; }
h2 { margin: 8px 0 5px 0; font-size: 12pt; page-break-before: auto; break-before: auto; }
.prospective-intervals-heading { page-break-before: auto; break-before: auto; }
.candidate-detail { page-break-inside: avoid; break-inside: avoid; }
"""
    if table:
        table_font = "6.8pt" if compact_table else "7.2pt"
        table_padding = "2px" if compact_table else "3px"
        overrides += f"""
table {{ font-size: {table_font}; border-collapse: collapse; }}
th, td {{ padding: {table_padding}; }}
tr {{ page-break-inside: avoid; break-inside: avoid; }}
"""
    html = (
        "<html><head><meta charset='utf-8'><style>"
        + style
        + "\n"
        + overrides
        + "</style></head><body>"
        + fragment
        + "</body></html>"
    )
    document = QTextDocument()
    document.setDocumentMargin(0.0)
    document.setDefaultFont(print_font(9.0, text=html))
    document.setTextWidth(width)
    document.setHtml(html)
    layout = document.documentLayout()
    if layout is None:
        raise RuntimeError("Не удалось рассчитать компоновку текста отчёта")
    return document, float(layout.documentSize().height())


def _document_style(html: str) -> str:
    match = _STYLE_PATTERN.search(html)
    return match.group(1) if match else ""


def _top_level_body_blocks(html: str) -> tuple[str, ...]:
    match = _BODY_PATTERN.search(html)
    body = match.group(1) if match else html
    blocks: list[str] = []
    depth = 0
    start: int | None = None
    for tag in _TAG_PATTERN.finditer(body):
        token = tag.group(0)
        if token.startswith(("<!--", "<!")):
            continue
        closing = bool(tag.group(1))
        name = tag.group(2).casefold()
        self_closing = token.rstrip().endswith("/>") or name in _VOID_TAGS
        if not closing:
            if depth == 0:
                start = tag.start()
            if not self_closing:
                depth += 1
            elif depth == 0 and start is not None:
                blocks.append(body[start : tag.end()].strip())
                start = None
        else:
            depth = max(0, depth - 1)
            if depth == 0 and start is not None:
                blocks.append(body[start : tag.end()].strip())
                start = None
    return tuple(block for block in blocks if block)


def _table_parts(table_html: str) -> _TableParts:
    opening_match = re.match(r"\s*(<table\b[^>]*>)", table_html, re.I | re.S)
    opening = opening_match.group(1) if opening_match else "<table>"
    colgroup_match = _COLGROUP_PATTERN.search(table_html)
    thead_match = _THEAD_PATTERN.search(table_html)
    tbody_match = _TBODY_PATTERN.search(table_html)
    body = tbody_match.group(1) if tbody_match else table_html
    return _TableParts(
        opening,
        colgroup_match.group(0) if colgroup_match else "",
        thead_match.group(0) if thead_match else "",
        tuple(_ROW_PATTERN.findall(body)),
    )


def _table_html(parts: _TableParts, rows: tuple[str, ...]) -> str:
    return (
        parts.opening
        + parts.colgroup
        + parts.thead
        + "<tbody>"
        + "".join(rows)
        + "</tbody></table>"
    )


def _is_heading(block: str) -> bool:
    return bool(re.match(r"\s*<h[1-6]\b", block, re.I))


def _is_notice(block: str) -> bool:
    return bool(
        re.match(
            r"\s*<div\b[^>]*class=[\"'][^\"']*notice",
            block,
            re.I,
        )
    )


__all__ = ["render_report_html"]
