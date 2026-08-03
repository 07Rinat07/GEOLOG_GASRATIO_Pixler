# Print, gas-curve, and GeoScape time regression matrix

This regression set is based on the operator-supplied LAS, Paradox DB, GeoScape/GeoScape II containers, diagnostics, screenshots, and malformed PDF exports reviewed on 2026-08-04.

## Required invariants

- Sparse derived gas calculations must not be joined across long intervals without valid updates.
- Short missing runs may remain visually continuous only within the configured acquisition-step tolerance.
- Real source-axis outages must remain hard breaks.
- A time-only GeoScape table must select its TIME/DATETIME candidate; a weak monotonic sensor must never become an artificial depth axis.
- Report interval boundaries must accept canonical ISO datetime text and finite Unix-second viewport values.
- Raw timestamp audit channels must not appear as ordinary parameter curves in generated forms.
- Calendar and relative-time rulers must reserve enough width for readable labels in the UI and PDF output.
- Automatic pagination must not produce a nearly empty final page when the remainder can be distributed without a material scale change.
- A repeated final-page column header must not contain graph pixels, move away from the page bottom, or change the canonical column width.
- The screen-only “no numeric data” overlay must be hidden during print capture so it cannot be clipped into continuation-page graph bodies; the track title remains the printed diagnostic.
- Print fonts must never receive a non-positive point size.

## Automated coverage

The focused tests cover datetime boundary normalization, GeoScape time-only automatic mapping, sparse gas continuity, automatic tail-page balancing, semantic header cropping, screen-only no-data overlays, print-font clamping, time-ruler geometry, and form materialization.

The Windows release gate remains the acceptance authority for Qt rendering, HiDPI behavior, generated PDFs, and screenshot artifacts.
