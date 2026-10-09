# Print and Export Center

Both interpretation report preview depth axes use the shared profile's fonts and colours. Complete negative and long values fit the existing label areas; tick positions and depth values remain unchanged.

The interpretation report preview title and explanatory footer use the shared profile's typography and colours. Enlarged fonts fit the measured width and height while retaining complete text and the existing chart arrangement.

The gas-context track heading uses the shared table font size. Standard, OPUS and preview reserve space using the same font that draws the complete wrapped heading; event codes and depths retain their existing presentation.

The gas-context legend uses the shared typography profile for its heading and event rows. Enlarged headings are measured for preview layout and PDF pagination; complete identifiers, depths and localized event names are retained.

The simple Masterlog footer and the document-control footer use the shared print profile's footer font size. The document-control header retains table typography; page numbers, branding and compact metadata occupy their existing reserved areas.

The automatic Masterlog document-control area and footer select the print font from each complete label before measuring and shortening it. Russian, Kazakh and English values retain the shared print font stack, physical sizes and placement; long metadata remains shortened only within bounded fields.

Haworth/Pixler depth groups differ by filled marker shape and line pattern as well as colour. Both legends show matching samples so observations and profiles can be identified in monochrome print.

Haworth/Pixler chart headings, scales, legends and explanatory text use the shared typography profile. Enlarged font sizes are fitted to measured field bounds, retaining complete labels and missing-data messages.

The Haworth/Pixler chart background, text, grid and frames use the shared report palette. Depth colours are retained to match observations, profiles and legend entries; text sizes and chart geometry remain unchanged.

Haworth/Pixler correlation chart text retains its physical size as print DPI changes. Labels, scales and depth profiles remain complete; the PNG preview keeps its existing scaling.

The gas mixture chart title, scales, legend and time axis use the shared typography profile. Larger font sizes are fitted to measured field bounds, preserving full labels and the chart geometry.

The gas mixture time chart distinguishes C1–C5 by line pattern as well as colour. Legend samples match the curves, allowing components to be identified in monochrome print. Colours and numerical values are preserved.

Geology PDF headings retain the point sizes of the shared visual profile. Body text and tables use their profile roles; wrapped titles and geologist conclusions remain complete.

Simple tablet print headers and footers use physical points from the shared profile. Gaps between title/range and brand/page number remain stable across DPI. Long titles and brands are elided while the range and page number remain complete. Pixel previews and pagination settings are preserved.

## Unified execution boundary — 0.7.30

Preview, physical printing, PDF, and paged raster/SVG export now run through one
`PrintJobExecutor`. The user workflow, page settings, overwrite confirmation, and cancellation
messages are unchanged; the refactoring prevents the main-window commands from diverging from
the shared renderer.

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

## Print model 0.7.38

Print Center supports A4/A3/custom/roll, Fit, and 100%. At 100%, source form widths are preserved and wide forms become numbered continuations with overlap. After the native dialog, the physical printer gate validates media, bounds, margins, printable area, and DPI. See [Print media and scale model](PRINT_MEDIA_MODEL.md).

## Windows release acceptance

Before a stable release, the automated matrix starts Print Center in separate processes for
Windows/Qt scale factors 100%, 125%, 150%, and 200%. It covers A4, A3, and roll media, portrait and
landscape, Fit and 100%, continuation pages, RU/KK/EN Unicode, PDF output, and a test-widget
screenshot. Evidence and `windows-release-checklist.json` are written only below
`build/ci-artifacts/windows-acceptance`; they are not committed or included as source artifacts.

The automated result remains `pending_physical_printer` until an engineer selects a real printer,
sends the acceptance sheet, and visually confirms margins, clipping, readability, colour, and page
order. Physical confirmation uses `--printer`, `--operator`, `--print-test`,
`--confirm-physical-output`, and `--require-physical` with `tools/windows_release_matrix.py`.
Without that evidence, REL-03 is not complete.

