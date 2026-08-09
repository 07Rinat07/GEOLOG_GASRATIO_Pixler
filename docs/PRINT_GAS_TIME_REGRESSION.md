# Print, gas-curve, and GeoScape time regression matrix

This regression set is based on the operator-supplied LAS, Paradox DB, GeoScape/GeoScape II containers, diagnostics, screenshots, and malformed PDF exports reviewed on 2026-08-04 and rechecked with the 2026-08-09 files.

## Required invariants

- Sparse derived gas calculations must not be joined across long intervals without valid updates.
- Finite samples outside a configured linear or logarithmic range must remain in the continuous polyline inside a bounded off-screen overscan and be clipped by the track viewport. They must not become `NaN` islands, an edge plateau, unsafe painter coordinates, artificial strokes, or dots.
- Real `NaN`, nonfinite axis rows, and non-positive logarithmic values remain hard visual gaps.
- Short missing runs may remain visually continuous only within the configured acquisition-step tolerance.
- Real source-axis outages must remain hard breaks.
- A time-only GeoScape table must select its TIME/DATETIME candidate; a weak monotonic sensor must never become an artificial depth axis.
- Report interval boundaries must accept canonical ISO datetime text and finite Unix-second viewport values.
- Raw timestamp audit channels must not appear as ordinary parameter curves in generated forms.
- Calendar and relative-time rulers must reserve enough width for readable labels in the UI and PDF output.
- Automatic pagination must not produce a nearly empty final page when the remainder can be distributed without a material scale change.
- A repeated final-page column header must not contain graph pixels, move away from the page bottom, or change the canonical column width.
- A dense C1–nC5 header must print every configured component row in both the first-page and repeated final-page copies; the body must end before the lower copy begins.
- A short final page must temporarily relax the interactive plot minimum height, then restore it after capture; child plot geometry must never overflow the page snapshot.
- The screen-only “no numeric data” overlay must be hidden during print capture so it cannot be clipped into continuation-page graph bodies; the track title remains the printed diagnostic.
- Horizontal track titles must reserve their actual word-wrapped height before the common header band is synchronized; neither the first-page title nor its repeated final-page copy may be clipped.
- Title height must be recalculated after every adaptive paper-width pass because wrapping can change when the form columns are fitted to the page.
- Print fonts must never receive a non-positive point size.

## Automated coverage

The focused tests cover datetime boundary normalization, GeoScape time-only automatic mapping, sparse gas continuity, bounded off-scale viewport clipping, extreme-outlier painter safety, automatic tail-page balancing, practical full-day time pagination, stable repeated page capture, complete seven-row final-page legends, short-page plot overflow, bounded print-job size, CPU-backed track capture, settled plot-boundary header cropping, screen-only no-data overlays, wrapped title geometry, adaptive-width title resynchronization, print-font clamping, time-ruler geometry, and form materialization.

The Windows release gate remains the acceptance authority for Qt rendering, HiDPI behavior, generated PDFs, and screenshot artifacts.
