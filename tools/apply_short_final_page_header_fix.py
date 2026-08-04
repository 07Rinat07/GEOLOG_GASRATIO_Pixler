from __future__ import annotations

from pathlib import Path


def replace_once(path: Path, old: str, new: str) -> None:
    text = path.read_text(encoding="utf-8")
    count = text.count(old)
    if count != 1:
        raise SystemExit(f"{path}: expected one patch anchor, found {count}")
    path.write_text(text.replace(old, new, 1), encoding="utf-8")


def main() -> None:
    tablet_print = Path("src/geoworkbench/printing/tablet_print.py")
    replace_once(
        tablet_print,
        '''        if target_content_height is not None:
            minimum_height = header_height + 1
            desired_height = max(minimum_height, int(target_content_height))
            for _attempt in range(3):
                current_height = max(item.widget.height() for item in rendered)
                delta = desired_height - current_height
                if abs(delta) <= 1:
                    break
                tablet.resize(
                    max(1, tablet.width()),
                    max(1, tablet.height() + delta),
                )
                _activate_layout_tree(tablet)
                tablet.refresh_shared_vertical_rulers()
            content_height = max(item.widget.height() for item in rendered)
            header_height = print_title_band + print_header_band
''',
        '''        requested_body_height: int | None = None
        if target_content_height is not None:
            # Preserve the graph body requested by pagination. Adaptive print
            # widths can wrap titles and increase the final header after this
            # initial measurement; settle the viewport as final header + body.
            requested_body_height = max(
                1,
                int(target_content_height) - header_height,
            )
''',
    )
    replace_once(
        tablet_print,
        '''        for _attempt in range(3):
            for item, width in zip(rendered, layout.widths, strict=True):
                item.widget.set_track_width(width)
            print_title_band = max(
                item.widget.natural_title_header_height for item in rendered
            )
            for item in rendered:
                item.widget.set_synchronized_title_header_height(print_title_band)
            _activate_layout_tree(tablet)
            tablet.refresh_shared_vertical_rulers()
            measured_header_height = print_title_band + print_header_band
            next_layout = build_layout(measured_header_height)
            header_height = measured_header_height
            if next_layout == layout:
                break
            layout = next_layout

        print_ruler_layout = tablet.refresh_shared_vertical_rulers()
''',
        '''        for _attempt in range(6):
            for item, width in zip(rendered, layout.widths, strict=True):
                item.widget.set_track_width(width)
            _activate_layout_tree(tablet)

            # Width fitting can change both wrapped track titles and curve
            # header controls. Remeasure and synchronize both bands before
            # deciding the hidden viewport height.
            print_title_band = max(
                item.widget.natural_title_header_height for item in rendered
            )
            print_header_band = max(
                item.widget.natural_curve_header_height for item in rendered
            )
            for item in rendered:
                item.widget.set_synchronized_title_header_height(print_title_band)
                item.widget.set_synchronized_header_height(print_header_band)
            _activate_layout_tree(tablet)
            tablet.refresh_shared_vertical_rulers()

            measured_header_height = print_title_band + print_header_band
            current_height = max(item.widget.height() for item in rendered)
            desired_height = current_height
            if requested_body_height is not None:
                desired_height = measured_header_height + requested_body_height
            elif current_height <= measured_header_height:
                desired_height = measured_header_height + 1

            delta = desired_height - current_height
            if abs(delta) > 1:
                tablet.resize(
                    max(1, tablet.width()),
                    max(1, tablet.height() + delta),
                )
                _activate_layout_tree(tablet)
                tablet.refresh_shared_vertical_rulers()

            content_height = max(item.widget.height() for item in rendered)
            if content_height <= measured_header_height:
                tablet.resize(
                    max(1, tablet.width()),
                    max(
                        1,
                        tablet.height()
                        + measured_header_height
                        + 1
                        - content_height,
                    ),
                )
                _activate_layout_tree(tablet)
                tablet.refresh_shared_vertical_rulers()
                content_height = max(item.widget.height() for item in rendered)

            next_layout = build_layout(measured_header_height)
            header_height = measured_header_height
            height_is_stable = (
                requested_body_height is None
                or abs(content_height - desired_height) <= 1
            )
            if next_layout == layout and height_is_stable:
                break
            layout = next_layout

        content_height = max(item.widget.height() for item in rendered)
        if not 0 < header_height < content_height:
            raise TabletPrintError(
                "После адаптации печатной формы шапка не оставляет места для графика"
            )

        print_ruler_layout = tablet.refresh_shared_vertical_rulers()
''',
    )
    replace_once(
        tablet_print,
        '''        for item, logical_width in zip(rendered, layout.widths, strict=True):
            logical_height = max(1, item.widget.height())
            pixel_size = QSize(
''',
        '''        for item, logical_width in zip(rendered, layout.widths, strict=True):
            # Every track uses one canonical height, so the repeated-header crop
            # cannot include graph pixels from a differently sized column.
            logical_height = content_height
            pixel_size = QSize(
''',
    )

    page_renderer = Path("src/geoworkbench/printing/page_renderer.py")
    replace_once(
        page_renderer,
        '''        y = content_rect.top() + (content_rect.height() - rendered_height) / 2.0
        region_width = rendered_width
''',
        '''        # Keep a short final graph body at the top of the sheet. The
        # repeated form legend is anchored independently at the bottom.
        y = content_rect.top()
        region_width = rendered_width
''',
    )
    replace_once(
        page_renderer,
        '''    repeated_header = QRectF(
        x,
        body.bottom() + gap_target_height,
        region_width,
        header_target_height,
    )
''',
        '''    repeated_header_top = (
        content_rect.bottom() - header_target_height
        if scale_mode is PrintScaleMode.FIT
        else body.bottom() + gap_target_height
    )
    repeated_header = QRectF(
        x,
        repeated_header_top,
        region_width,
        header_target_height,
    )
''',
    )

    regression = Path("tests/test_real_tablet_pdf_regressions.py")
    text = regression.read_text(encoding="utf-8")
    import_anchor = "from geoworkbench.printing.print_layout import PrintScaleMode\n"
    if "capture_tablet_print_snapshot" not in text:
        text = text.replace(
            import_anchor,
            import_anchor
            + "from geoworkbench.printing.tablet_print import "
            + "capture_tablet_print_snapshot\n",
            1,
        )
    test_block = '''


def test_short_partial_snapshot_reflows_header_and_uses_one_canonical_height(
    qapp,
) -> None:
    tablet = _complex_tablet(domain=DepthDomain.MD, start=1174.8, end=1482.4)
    tablet.show()
    qapp.processEvents()
    try:
        snapshot = capture_tablet_print_snapshot(
            tablet,
            page_aspect_ratio=0.65,
            fit_columns=True,
            raster_scale=2.5,
            show_column_header=False,
            repeat_column_header_at_bottom=True,
            target_content_height=120,
            layout_content_height=900,
        )
    finally:
        tablet.close()
        qapp.processEvents()

    assert 0 < snapshot.header_height < snapshot.content_height
    expected_pixel_height = round(snapshot.content_height * snapshot.raster_scale)
    assert all(pixmap.height() == expected_pixel_height for pixmap in snapshot.pixmaps)
'''
    if "test_short_partial_snapshot_reflows_header_and_uses_one_canonical_height" not in text:
        text += test_block
    regression.write_text(text, encoding="utf-8")

    Path("tests/test_short_final_page_header_geometry.py").write_text(
        '''from __future__ import annotations

from PySide6.QtCore import QRectF
from PySide6.QtGui import QColor, QImage, QPainter, QPixmap

import geoworkbench.printing.page_renderer as page_renderer
from geoworkbench.printing.form_column_layout import AdaptiveColumnLayout
from geoworkbench.printing.print_layout import PrintScaleMode
from geoworkbench.printing.tablet_print import TabletPrintSnapshot


def test_short_final_page_anchors_repeated_header_to_bottom(qapp, monkeypatch) -> None:
    pixmap = QPixmap(200, 300)
    pixmap.fill(QColor("white"))
    snapshot = TabletPrintSnapshot(
        (pixmap,),
        AdaptiveColumnLayout((200,), spacing=0),
        content_height=300,
        header_height=80,
    )
    body_rects: list[QRectF] = []
    header_rects: list[QRectF] = []
    monkeypatch.setattr(
        page_renderer,
        "paint_tablet_snapshot",
        lambda _painter, rect, *_args, **_kwargs: body_rects.append(QRectF(rect)),
    )
    monkeypatch.setattr(
        page_renderer,
        "paint_tablet_header_repeat",
        lambda _painter, rect, *_args, **_kwargs: header_rects.append(QRectF(rect)),
    )

    canvas = QImage(400, 800, QImage.Format.Format_ARGB32)
    canvas.fill(QColor("white"))
    painter = QPainter(canvas)
    page = QRectF(0.0, 0.0, 400.0, 800.0)
    try:
        page_renderer._paint_tablet_with_repeated_header(
            painter,
            page,
            snapshot,
            scale_mode=PrintScaleMode.FIT,
            continuation=None,
            show_column_header=False,
        )
    finally:
        painter.end()

    assert len(body_rects) == 1
    assert len(header_rects) == 1
    assert body_rects[0].top() == page.top()
    assert header_rects[0].bottom() == page.bottom()
    assert body_rects[0].bottom() < header_rects[0].top()
''',
        encoding="utf-8",
    )


if __name__ == "__main__":
    main()
