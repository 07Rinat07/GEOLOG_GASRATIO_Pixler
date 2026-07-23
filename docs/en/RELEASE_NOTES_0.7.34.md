# Release notes 0.7.34 — Report Passport

Date: 23 July 2026. Status: test build.

## New

- added deterministic `ReportPassport` schema v1 with canonical JSON and SHA-256;
- captures source fingerprints, exact interval, selected channel values, complete semantic
  bindings/UOM, formula versions, form revision, language, and render settings;
- channel fingerprints cover only samples inside the actual report interval;
- forms and tablet layouts use content-addressed revisions while Masterlog retains explicit version;
- absolute output paths and generation timestamps are excluded;
- `load_report_passport()` detects modified signed JSON.

## Export coverage

- Print Center writes `<output>.passport.json` for PDF and paged image exports;
- direct active-view PNG/SVG/PDF export writes the same sidecar;
- Masterlog PDF and interpretation PDF now write passports;
- physical printing computes and displays the digest without a sidecar;
- an existing sidecar participates in overwrite confirmation.

## Sources and safety

- uses import-time LAS fingerprints, embedded lossless LAS, or an available external-file
  fingerprint with an explicit warning;
- normalized report-data fingerprint is always included;
- sidecars are written atomically through a temporary file, `fsync`, and `os.replace`;
- project format remains v16.

## Verification

- 742 available headless/regression/source-integrity tests passed;
- 4 platform scenarios were skipped;
- 4 additional LAS/Qt scenarios were deselected because their dependencies are unavailable;
- `compileall` completed successfully;
- the full Ruff/mypy/Qt/LAS gate and Windows/HiDPI/PDF/physical-print smoke matrix remain required.
