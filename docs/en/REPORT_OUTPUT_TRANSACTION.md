# Recoverable report-file transaction

Status: implemented in version 0.7.39. Journal runtime schema: v1. Report Passport: schema v4.
Project format remains v16.

## Purpose

A report output and its `*.passport.json` are now committed as one recoverable operation. Most
filesystems cannot atomically replace several files at one instant, so the implementation uses a
journaled commit, complete rollback, and deterministic recovery after interruption or I/O failure.

Covered paths:

- Print Center PDF and paged PNG/JPEG/TIFF/BMP/WebP/SVG;
- direct visualization PNG/SVG/PDF;
- selected-interval CSV/XLSX;
- Masterlog PDF;
- interpretation PDF.

## Commit sequence

1. Recover any pending journal for the target.
2. Render only into a hidden staging directory beside the destination.
3. Validate non-empty outputs and safe relative names.
4. Hash the completed bytes and record size and MIME type.
5. Add `artifacts` to Report Passport schema v4 and re-sign it.
6. Write the sidecar in staging.
7. Journal all destinations and backups.
8. Move old files to backup and install staged files with `os.replace`.
9. Re-verify the installed files against passport fingerprints.
10. Mark `committed`, then remove backups, staging, and journal.

## Recovery

Before `committed`, recovery removes partially installed new files and restores the previous output,
sidecar, and obsolete continuation pages. If commit was already recorded, recovery keeps the new
pair and only completes cleanup.

The next export to the same target recovers automatically. Manual directory recovery:

```powershell
.\.venv\Scripts\python.exe tools\recover_report_transactions.py "C:\Reports"
```

## Output fingerprint

Each schema-v4 artifact records only a safe basename, `single-file` or `page` role, optional page
number, MIME type, byte size, and SHA-256 of the completed output. `load_report_passport()` verifies
both the JSON digest and every referenced output artifact, so later PDF/image/CSV/XLSX modification
is detected.

## Limits

- absolute paths exist only in the temporary recovery journal, never in the passport;
- recovery operations are restricted to the output directory and owned staging workspace;
- physical printing has no file and therefore no output fingerprint;
- this is not an organizational digital signature or trusted timestamp;
- Windows/network-filesystem smoke tests remain mandatory.

## DOCX and HTML in 0.7.40

DOCX and HTML are produced only in staging and installed together with Passport v4. The
transaction verifies a non-empty completed file, calculates MIME, size, and SHA-256, and restores
the previous document and sidecar after a failure.
