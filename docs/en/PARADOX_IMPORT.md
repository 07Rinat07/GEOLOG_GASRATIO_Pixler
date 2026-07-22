# GeoScape / Borland Paradox DB import — 0.7.16

## Purpose

The importer converts GeoScape/Borland Paradox tables into the existing GEOLOG GASRATIO@Pixler multi-index `Dataset` model. After index confirmation, the standard table, graphs, LAS editor, project storage, merge, tablets, and printing are used; no parallel editor or duplicate curve model is created.

## Opening data

Use **File → Import → GeoScape / Paradox DB**, universal import, or drag a `.db` file into the window. The extension is not trusted: SQLite is checked first, then bounded Paradox binary structure. DB/PX/TV/FAM sources are opened read-only and never overwritten.

Selecting `BLData.db` discovers case-insensitive same-name `BLData.PX`, `BLData.TV`, and `BLData.FAM`. Missing companions produce a warning but do not block DB-only import.

## Analysis dialog

The dialog shows format, version, size, row/field counts, and bundle files. The channel table controls inclusion, LAS mnemonic, description, and unit. Preview loads only the first and last 20 rows. Reading, analysis, and dataset creation run in worker threads with progress and cancellation.

Depth and time candidates are scored by completeness, monotonicity, range, step stability, name, duplicates, and reversals. Users can always replace the proposed index; ambiguous candidates are classified as mixed and are not silently converted. OLE/Delphi Automation date, Unix scales, and relative seconds/milliseconds are supported. A numeric elapsed `TIME` index is created while the original numeric source is retained as `<channel>_RAW`.

## Channels and profiles

Unknown `Sxxx` channels are not guessed: the source code remains the mnemonic, unit stays empty, and the description identifies the source channel. A JSON dictionary stores confirmed mappings, with user entries taking priority. Import profiles store an exact SHA-256 schema signature, indexes, mappings, NULL, and processing rules; they are applied only to an exact structure match.

## Quality control

The analyzer checks empty channels/rows, NaN/Infinity, huge values, statistical outliers, duplicate/reverse/negative depth, jumps, and chronology. Duplicate depth is kept by default. Explicit policies are keep all, first, last, mean, and median; applied removals are recorded in dataset metadata and logs. The protocol also records the schema signature, selected indexes, NULL, sorting, imported/skipped channel and row counts, diagnostic severity counts, and every explicit correction.

## LAS and TIME → DEPTH

Depth export writes the active index first as `DEPT.M`; `STRT`, `STOP`, and a median positive `STEP` are derived from data. Time export writes `TIME.SEC`, stores the initial date/time in the header, and retains depth as `DEPTH.M`.

**Convert time data to depth** creates a new derived dataset without modifying the source. Methods are first, last, mean, median, minimum, maximum, nearest, and explicit linear interpolation. Missing bins are not aggressively filled unless linear interpolation is selected.

## Batch conversion

**Tools → Batch DB → LAS conversion** accepts files or directories, recursive search, a profile, depth/time output, `{source_name}_{mode}.las` naming, skip/overwrite protection, progress, cancellation, and a JSON log next to the result. An ambiguous file without a matching profile is reported for manual configuration rather than guessed.

## Verified samples and limitations

The supplied samples verify Paradox 7.x `NUMBER` and `LONG`: `BLData.db` has 3488 rows/70 fields and `D250.db` has 1739/101. The implementation also contains bounded best-effort decoding for Alpha, Date, Short, Logical, Time, Timestamp, AutoIncrement, BCD, and Bytes/Blob, but those types were not present in the supplied samples and require additional real-world validation. A field-level decode error is logged and must not crash the application.
