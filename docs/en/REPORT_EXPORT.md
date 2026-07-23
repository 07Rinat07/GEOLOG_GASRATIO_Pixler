# Report export and interval summary

Status: mandatory before the final release.

## Purpose

The subsystem must create a reproducible report for a selected well and depth range. It complements
rather than replaces the printable Masterlog by adding structured interval tables, statistics, and
appendices. Every value must come from persisted project data; missing values must never be turned
into zero or an invented geological description.

## Report types

1. **Interval geology report** — stratigraphy, lithology, cuttings composition, manually entered
   rock description, LBA, calcimetry, core and depth events.
2. **Gas geochemistry report** — component gases, total gas, Gas Ratio, relative composition,
   normalized curves, H₂S/CO₂ when available, coverage and quality diagnostics.
3. **Drilling-technology report** — ROP, WOB, RPM, flow, pressure, torque, mud properties and any
   other available engineering channels.
4. **Combined well report** — selected sections, interval table, plots, header, legends and
   Masterlog appendices.

## Mandatory fields in an interval row

- well, asset, field/area and report profile;
- top, bottom, thickness and depth unit;
- stratigraphic rank, code and name;
- lithotype, cuttings fractions and sample identifier;
- only a manually saved rock description or a template explicitly inserted by the user;
- LBA intensity/score, colour, bitumen, cut, residue, odour, observation and manual conclusion;
- calcite CaCO₃, dolomite CaMg(CO₃)₂ and insoluble residue;
- C1–C5, total gas, absolute and relative Gas Ratio/Pixler outputs, H₂S/CO₂ and other available gases;
- drilling and mud parameters;
- events such as shows, losses, gains, core, casing shoe and cementing;
- source, formula/version, units, coverage and quality warnings.

## Interval construction

The user may select a custom top–bottom range, cuttings intervals, lithology intervals,
stratigraphic intervals, the union of all interval/event boundaries, or a fixed depth step.
Numeric channels support real-point count, coverage, minimum, maximum, mean, median and extremum
depths, with optional percentiles. Gaps and `NULL/NaN` values must not be bridged without an
explicit interpolation policy. A measured zero remains distinct from a missing measurement.

## Report designer

The Constructor receives a dedicated Reports tab for report profile, sections, well, depth range,
interval policy, parameters, statistics, RU/KK/EN language, units, number formats, page profile,
orientation, header, plots, legends, images, Masterlog appendices, preview and preflight.

## Export formats

PDF for final printing, DOCX for editing, XLSX for interval/detail tables, CSV/TSV for exchange,
HTML for local interactive viewing, and PNG/SVG/PDF appendices for plots and Masterlog pages.

## Quality rules

- report values must match the tablet at the same depth;
- units, formulas and calculation versions are retained as metadata;
- automatic rock-description fallback is forbidden;
- missing data is reported as missing, never as zero;
- identical inputs produce deterministic outputs;
- preflight blocks invalid intervals, unknown units, missing assets and broken bindings;
- PDF/DOCX/XLSX are tested for pagination, Cyrillic text, RU/KK/EN and long depth ranges.

## Implementation order

1. `ReportDefinition`, `IntervalReportRow` and interval-boundary union service.
2. Geology, cuttings, LBA, calcimetry, stratigraphy and manual-description summaries.
3. Gas and drilling-channel aggregation with quality metrics.
4. Reports tab, preview and preflight in the Constructor.
5. PDF/XLSX/CSV/TSV/DOCX/HTML through shared ReportDefinition, Coverage, and output transaction contracts.
6. Regression tests, tablet parity and physical Windows print verification.

## Implemented passport for current exports

Since 0.7.34, Print Center, direct PNG/SVG/PDF, Masterlog PDF, and interpretation PDF create a
deterministic JSON sidecar containing exact interval/channel values, source fingerprints,
semantic bindings/UOM, formula versions, form revision, language, and render settings. The shared
`ReportDefinition` reuses this contract. See [REPORT_PASSPORT.md](REPORT_PASSPORT.md).

## Shared ReportDefinition in 0.7.36

Print Center, Masterlog, and selected-interval CSV/XLSX now create and resolve one
`ReportDefinition` first. Dataset, index, curve IDs, form revision, language, and interval are not
recalculated between preview and the final artifact. See [REPORT_DEFINITION.md](REPORT_DEFINITION.md).

## Coverage in 0.7.37

CSV distinguishes `0`, an empty missing sample, and `#N/A` for an unavailable channel. XLSX exposes availability, observed, zeros, missing, and coverage on the `Parameters` sheet. See [Coverage model](COVERAGE_MODEL.md).

## Print model in 0.7.38

A4/A3/custom/roll, Fit, and 100% share one plan. At 100%, a wide form creates continuations while PDF and the printer remain one multi-page job. See [PRINT_MEDIA_MODEL.md](PRINT_MEDIA_MODEL.md).


## Recoverable output commit in 0.7.39

PDF, paged images/SVG, CSV/XLSX, Masterlog, and interpretation PDF render into staging and commit with the schema-v4 passport. Output bytes are fingerprinted before install; rollback restores the previous pair. See [Report output transaction](REPORT_OUTPUT_TRANSACTION.md).

## DOCX and HTML in 0.7.40

Selected-interval DOCX and HTML use the same `ResolvedReportDefinition` as CSV/XLSX. DOCX is
deterministic OOXML with no macros or external embedded objects; HTML is one UTF-8 file with
inline CSS and no scripts or network resources. Coverage keeps `0`, `—`, and `#N/A` distinct.
Output and Passport v4 are written in one recoverable transaction. See
[DOCX_HTML_EXPORT.md](DOCX_HTML_EXPORT.md).
