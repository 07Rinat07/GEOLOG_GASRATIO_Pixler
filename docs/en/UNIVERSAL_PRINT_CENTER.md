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

## Vertical range

The current tablet depth or time range is printed. Set a specific range with the visible-interval control and depth navigation before opening the center. “Full range” fits the complete range on one page. Automatic multi-page pagination of the full wellbore is planned as the next printing increment.

## Stored preferences

Page format, orientation, margins, column fitting, last file format, DPI, and quality are stored separately for the active engineer profile.
