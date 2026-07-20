# Print and Export Center

## Purpose

The Print and Export Center is the single window for preparing the active chart, tablet, or form for physical printing and file export. Open it through **File → Print and export center...** (`Ctrl+P`) or use **Print / export** in Form Manager.

## Supported destinations

- native physical printer through the standard Windows/Linux dialog;
- PDF;
- PNG;
- JPEG/JPG;
- TIFF;
- BMP;
- WebP;
- SVG.

The raster list follows the available Qt image plugins. PNG and TIFF are lossless; the quality percentage applies to JPEG/JPG and WebP.

## Page settings

A4, A3, custom media, and roll media with automatic length are available. Standard sheets support portrait and landscape orientation. Left, top, right, and bottom margins are independent. Resolution is selectable from 72 to 600 DPI.

Raster export creates the real paper pixel dimensions. For example, A4 at 300 DPI is approximately 2480 × 3508 pixels rather than a screenshot of the current window.

## Forms and columns

With **Fit form columns to page width** enabled, the renderer:

- captures every visible track, including tracks outside the horizontal viewport;
- applies a readable minimum width by track type;
- caps excessively wide screen columns;
- balances widths for the selected page orientation;
- uses one common scale without horizontal clipping;
- restores the original working tablet widths after output.

## Preview

Preview, the physical printer, PDF, SVG, and raster formats share one page renderer. The preview therefore matches the final document layout.

## Vertical range and multi-page output

Tablet output supports three modes:

- **Current range** — one page containing the depth/time window currently open on screen;
- **Full range** — the complete wellbore or time series is split into pages automatically;
- **Custom range** — output between explicitly entered start and end boundaries.

**Units per page** controls how many metres or active time-axis units are placed on each sheet. The default is `50`. Optional page overlap keeps formations and events visible across page boundaries. Track headers, the page range, and `Page N of M` are repeated on every page.

PDF and the physical printer produce one multi-page document. PNG, JPEG/JPG, TIFF, BMP, WebP, and SVG exports create numbered files `_page_001`, `_page_002`, and so on. The original on-screen viewport is restored after output.

## Unicode, encodings, and fonts

Qt receives Unicode strings from the application; the source LAS/CSV encoding must be resolved during import. A strict preflight runs before preview, printing, or export and checks:

- Russian, Kazakh, and English text;
- Cyrillic including Kazakh letters `Ә Ғ Қ Ң Ө Ұ Ү Һ І`;
- engineering symbols `° ± × ÷ ≤ ≥ ≈ ≠ µ Ω Δ φ ρ ² ³`;
- replacement character `U+FFFD`, unpaired surrogates, and forbidden control characters;
- typical UTF-8/Windows-1251 mojibake patterns;
- glyph availability in installed scalable fonts.

Font embedding is enabled for `QPrinter`. Headers and footers use a verified Unicode-capable system font stack. If a character cannot be rendered safely, output is stopped before a defective PDF is created and the missing characters are reported explicitly.

## Stored preferences

Page format, orientation, margins, column fitting, last file format, DPI, quality, range mode, units per page, and overlap are stored separately for the active engineer profile.
