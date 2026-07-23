# Report Passport

Status: available since 0.7.34. Coverage entered schema v2, print media entered schema v3, and
fingerprints of completed output artifacts entered schema v4 in 0.7.39. Project format remains v16.

## Purpose

Report Passport is a deterministic JSON sidecar describing the provenance of a PDF, image,
CSV/XLSX, or other report result. Unchanged data, definition, language, render settings, and output
bytes produce the same `passport_sha256`.

```text
report.pdf
report.pdf.passport.json
```

Physical printing has no file, so it can expose a preliminary digest without artifacts but does not
create a sidecar.

## Covered paths

- Print Center PDF and paged PNG/JPEG/TIFF/BMP/WebP/SVG;
- direct visualization PNG/SVG/PDF;
- selected-interval CSV/XLSX;
- Masterlog PDF;
- interpretation PDF;
- physical print digest without a file sidecar.

## Recorded provenance

The passport records project/well/dataset identity, exact index and interval, selected values,
semantic bindings and UOM, coverage, formulas, form/template/report-definition revision, locale,
render and print-media settings, source fingerprints, and schema-v4 output artifacts.

Each completed artifact stores only a safe basename, `single-file` or `page` role, optional page
number, MIME type, byte size, and SHA-256 of the actual output bytes.

## Verification and transaction

`load_report_passport()` verifies the JSON digest and every referenced output file. Output and
sidecar are installed through recoverable transaction schema v1:

```text
staging → fingerprint → signed passport → journaled backup/install
→ installed-file verification → committed → cleanup
```

A failure before `committed` restores the previous pair. A failure after `committed` keeps the new
pair and completes cleanup. See [Report output transaction](REPORT_OUTPUT_TRANSACTION.md).

## Determinism and limits

Timestamps, random IDs, and absolute output paths are excluded. This mechanism is not an
organizational digital signature or trusted timestamp. Physical printing has no output-file
fingerprint. Windows/NTFS/network-share/PDF/HiDPI/physical-print smoke tests remain mandatory.
