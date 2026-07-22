# Hotfix report 0.7.24 — Windows black tablet render regression

## Defect

The 0.7.23 OOP interaction rewrite left `TabletAnnotationOverlay` as a full-size translucent child over the track container. On Windows, Qt may not alpha-composite that child correctly with native PyQtGraph viewports, resulting in a black rectangle across the graph body while headers remain visible.

## Code change

`TabletAnnotationOverlay` now owns a sparse native `QRegion`:

1. the overlay starts with an empty mask;
2. visible annotation paint bounds are united into a sparse region;
3. the region is intersected with the graph-body content rectangle;
4. changes during drag/resize are coalesced by a 16 ms single-shot timer;
5. the overlay remains `WA_TransparentForMouseEvents`;
6. the OOP `TabletInteractionRouter` remains the only pointer-event owner.

## Regression tests

Added `tests/test_annotation_windows_render_mask.py` and updated overlay source-contract tests. These tests prevent exposing the full canvas as the overlay native region and prevent reintroducing mouse ownership.

## Important limitation

The current container has no PySide6 or pyqtgraph. Therefore this package is a test hotfix, not a Windows-validated stable release. Mandatory manual test: open a populated tablet, verify curves are visible, enable F4, create/move/resize an annotation, scroll, and verify the graph body never turns black.
