# Report Passport

Status: implemented in version 0.7.34. Passport schema: v1. Project format remains v16.

## Purpose

Report Passport is a deterministic JSON sidecar explaining which data and rendering settings
produced a concrete PDF, PNG, SVG, or Print Center result. Repeating a report with unchanged data,
form, language, and render settings produces the same `passport_sha256`.

```text
report.pdf
report.pdf.passport.json
```

Physical printing has no output path, so the application computes and displays the passport digest
without creating a sidecar file.

## Covered workflows

- Print Center PDF and paged PNG/JPEG/TIFF/BMP/WebP/SVG;
- direct active-view PNG, SVG, and PDF export;
- Masterlog PDF;
- interpretation PDF for samples, calcimetry, and LBA;
- physical printing: digest only.

Preview is not a final export and does not create a passport.

## Captured contract

- application and passport-schema versions;
- project, well, dataset, or well-level artifact identifiers;
- exact interval, included sample count, and index-values SHA-256;
- hashes of only the selected channel values inside the report interval;
- original/canonical mnemonic, canonical kind, quantity class, source/display/canonical UOM;
- sensor ID, semantic source, family/category, confidence, match method, aliases, and evidence;
- curve provenance, state, and version;
- formula ID, version, expression SHA-256, and source;
- form/template ID, explicit version or content-addressed revision, and definition SHA-256;
- RU/KK/EN language;
- renderer, format, DPI, page profile, orientation, margins, pagination, and extra options;
- stored import source, embedded lossless LAS, or available external-file fingerprints;
- an always-present normalized fingerprint of the actual report data.

## Source-fingerprint priority

1. Import-time `LasSourceSnapshot` — `stored-at-import`.
2. Embedded lossless LAS artifact — `embedded-project-artifact`.
3. Available CSV/Excel/Paradox/LAS file — `captured-at-report-time`, with a warning.
4. Normalized report data — always included.

Absolute paths are never persisted; only the file name is recorded. If the original file is no
longer available, the normalized project-data snapshot still identifies the values used.

## Determinism and validation

- canonical JSON uses sorted keys and rejects `NaN/Infinity` metadata;
- no timestamp or absolute output path is signed;
- numeric arrays are normalized to little-endian float64; NaN payloads and signed zero are normalized;
- the digest covers every field except `passport_sha256` itself;
- `load_report_passport()` recalculates the digest and rejects tampered JSON;
- sidecars use a temporary file, `fsync`, and atomic `os.replace`.

## Limitations

- the output and sidecar are individually atomic but are not one filesystem transaction;
- the passport is provenance evidence, not an organizational digital signature or certification;
- output-file hashing will be added after the shared `ReportDefinition` pipeline is established;
- the Windows/HiDPI/PDF/physical-print smoke matrix remains required for stable status.
