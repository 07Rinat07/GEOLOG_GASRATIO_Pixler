# GeoScape / Borland Paradox DB import

## Purpose and opening

The importer converts GeoScape/Borland Paradox tables into the standard `Dataset` model. Use
**File → Import → GeoScape / Paradox DB**, universal import, or drag a `.db` file into the window.
The extension is not trusted: SQLite is checked first, followed by the bounded Paradox binary
structure. Source DB/PX/TV/FAM files are opened read-only.

For `sample.db`, the application looks for `sample.PX`, `sample.TV`, and `sample.FAM`
case-insensitively. A missing companion is reported but does not block DB-only import.

## Security and resources

The header, record size, fields, blocks, declared capacity, and aggregate memory budget are
validated before arrays are allocated. Zero-sized fields, contradictory counters, truncated
blocks, and budget overruns are rejected. Reading, analysis, and `Dataset` creation run in a
cancellable worker; failure or closing cannot leave a partially registered dataset.

## Import Review

The dialog shows format, version, size, rows, fields, and companion files. Users select channels,
LAS mnemonics, descriptions, units, NULL rules, and the active TIME/DEPTH index. Preview reads only
the first and last 20 rows. An ambiguous index is never applied automatically.

OLE/Delphi Automation dates, Unix timestamps, and relative seconds/milliseconds are supported.
A numeric `TIME` index is created while the source number is retained as `<channel>_RAW`.

## Channels, profiles, and QC

Unknown `Sxxx` channels are not guessed. Confirmed mappings live in a dictionary; a profile stores
the schema SHA-256, indexes, mappings, NULL, and processing rules and is applied only to an exact
structure match.

Checks cover empty rows/channels, NaN/Infinity, outliers, duplicate/reverse/negative depth, jumps,
and chronology. Duplicates are retained by default; first/last/mean/median require an explicit
choice. Every correction and row count is recorded in provenance.

## Actual step and resampling

The nominal GeoScape 0.2 m grid is displayed separately from the source's actual step. The LAS
`STEP` header always describes rows that exist. A derived 0.2 m grid is created only through
**LAS Editor → Resample depth…**; the source DB and imported `Dataset` remain unchanged.

## LAS, TIME → DEPTH, and batch

Depth LAS uses `DEPT.M`, while time LAS uses `TIME.SEC`; `STRT/STOP/STEP` are derived from data.
TIME → DEPTH creates a separate derived dataset with first/last/mean/median/min/max, nearest, or
linear methods.

**Tools → Batch DB → LAS conversion** supports files/directories, recursive search, profiles,
`{source_name}_{mode}.las`, overwrite protection, progress, cancellation, and a JSON log.
An ambiguous file receives **Configuration required**.

## Limitations

Synthetic fixtures cover `NUMBER`, `LONG`, and bounded decoders for Alpha, Date, Short, Logical,
Time, Timestamp, AutoIncrement, BCD, and Bytes/Blob. Field validation uses anonymized tables only;
those files and conversion outputs are not stored in Git.
