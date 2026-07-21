# Roadmap — GEOLOG Gas Ratio & Pixler

Updated: 21 July 2026

## Current: GeoData depth workspace

Completed:

- curated factory-form library;
- merged Geology, Technology, and Gas Data headers;
- one synchronized depth coordinate and parameter-header band;
- exact template column order without a forced pinned depth track;
- Shift-drag creation and double-click re-editing of lithology;
- shared cuttings/LBA/calcimetry/description sample editor;
- rich text, symbols, images, deletion, and atomic update by `sample_id`;
- laptop-safe main-window geometry, horizontal form scrolling, and collapsible inspector;
- correct distinction between real zero and missing curve data;
- layout codec v10 and RU/KK/EN documentation.

## Next: unified Masterlog designer

- one model for screen form, print preview, PDF, raster/SVG export, and physical printing;
- editable report header with dynamic well fields, logos, legends, lines, and images;
- unified symbol catalog for lithology, LBA, oil/gas shows, core, mud losses/gains, casing, and markers;
- exact page/roll layout tests and Windows print-engine verification.

## Then: report export and interval summaries

- one `ReportDefinition` for geology, gas, drilling and combined reports;
- exact top/bottom/thickness rows for lithology, cuttings, LBA, calcimetry, stratigraphy and manual descriptions;
- C1–C5, total gas, absolute/relative Gas Ratio and Pixler outputs, H₂S/CO₂, drilling and mud channels;
- configurable aggregation with coverage and strict zero-vs-missing handling;
- Reports tab in the Constructor with preview, preflight and PDF/DOCX/XLSX/CSV/TSV/HTML export;
- tablet parity, provenance, calculation-version metadata and Windows print verification.

## Then: Gas Ratio & Pixler interpretation

- dedicated multi-track Gas Ratio/Pixler workspace;
- input-quality diagnostics and required-curve preparation;
- controlled, explainable fluid classification;
- oil/gas/condensate/uncertain markers with manual confirmation;
- interval table, legend, provenance, and printable report.

## Release hardening

- real LAS files from multiple vendors;
- 1366×768, 1920×1080, 2560×1440, and HiDPI screen matrix;
- 100k/1M/5M performance budgets;
- migration tests for old projects and hidden legacy forms;
- Windows installer and physical-printer regression;
- final RU/KK/EN documentation audit.

## Deferred

WITSML, DLIS, 3D, cloud synchronization, and multi-well correlation remain outside the current
release path unless separately prioritized.
