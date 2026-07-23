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
5. PDF and XLSX, followed by DOCX/HTML/CSV/TSV.
6. Regression tests, tablet parity and physical Windows print verification.

## Implemented passport for current exports

Since 0.7.34, Print Center, direct PNG/SVG/PDF, Masterlog PDF, and interpretation PDF create a
deterministic JSON sidecar containing exact interval/channel values, source fingerprints,
semantic bindings/UOM, formula versions, form revision, language, and render settings. The future
shared `ReportDefinition` must reuse this contract. See [REPORT_PASSPORT.md](REPORT_PASSPORT.md).
