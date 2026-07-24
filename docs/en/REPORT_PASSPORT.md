# Report Passport

Status: available since 0.7.34. Coverage entered schema v2, print media entered schema v3, and
completed output-artifact fingerprints entered schema v4 in 0.7.39.

## Purpose

Report Passport is a deterministic JSON sidecar that describes the provenance of a PDF, image,
CSV/XLSX, DOCX/HTML, or another report result. Unchanged data, ReportDefinition, locale, render
settings, and output bytes produce the same `passport_sha256`.

```text
report.pdf
report.pdf.passport.json
```

Physical printing creates no file, so it exposes only a preliminary digest without an output
artifact or file sidecar.

## Covered workflows

- Print Center PDF and paged PNG/JPEG/TIFF/BMP/WebP/SVG;
- active-visualization PNG/SVG/PDF;
- selected-interval CSV/XLSX;
- Masterlog PDF;
- interpretation PDF;
- DOCX and HTML through the shared report contract;
- physical-print digest without a file sidecar.

## Recorded provenance

- application and passport-schema versions;
- project, well, dataset, or well-level artifact identity;
- index, exact interval, sample count, and index-value SHA-256;
- fingerprints of actual selected-channel values;
- semantic bindings, UOM, sensor/source, confidence, aliases, and evidence;
- coverage: availability, observed, zeros, missing, and unavailable;
- formulas, versions, and expression SHA-256;
- form/template/report-definition revision and SHA-256;
- RU/KK/EN locale;
- renderer, format, DPI, media, orientation, margins, Fit/100%, and continuations;
- source/import/lossless fingerprints;
- completed-artifact basename, role/page, MIME, byte size, and SHA-256.

## Source-fingerprint priority

1. `LasSourceSnapshot` — `stored-at-import`.
2. Embedded lossless LAS artifact — `embedded-project-artifact`.
3. Available external CSV/Excel/Paradox/LAS — `captured-at-report-time`.
4. Normalized snapshot of the actual report data — always.

Absolute source and output paths are excluded from the passport.

## Verification and file transaction

The passport is finalized only after output is written to staging. Each file stores a safe basename,
`single-file` or `page` role, optional page number, MIME type, size, and SHA-256 of the actual bytes.

`load_report_passport()` verifies the JSON digest, output existence, size, and SHA-256. Output and
sidecar are installed through recoverable transaction schema v1:

```text
staging → output fingerprint → signed passport → journaled backup/install
→ installed-file verification → committed → cleanup
```

A failure before `committed` restores the previous pair. A failure after `committed` keeps the new
pair and completes cleanup. See [Report output transaction](REPORT_OUTPUT_TRANSACTION.md).

## Determinism

- JSON is canonicalized with sorted keys;
- timestamps, random IDs, and absolute output paths are excluded;
- `NaN`, Infinity, and signed zero are normalized in engineering fingerprints;
- the digest is calculated over the payload without `passport_sha256`;
- fingerprints depend on the selected interval and completed output bytes.

## Saving and later verification

A passport is created after a successful report export. It does not replace saving the project with
**Ctrl+S**. Keep output and sidecar together and reopen the sidecar through the supported verification
command. The pair may be moved because absolute output paths are excluded; renaming or changing the
output causes fingerprint verification to fail.

## Limits

- this is not an organizational digital signature or trusted timestamp;
- physical printing has no output-file fingerprint;
- a recovery journal may contain temporary absolute paths, but they are not part of the passport;
- Windows/NTFS/network-share/PDF/HiDPI/physical-print smoke testing remains mandatory before stable.
