# GeoScape / Borland Paradox DB import — 0.7.27

> 0.7.27 does not change Paradox logic; this release fixes tablet annotation deletion and view scoping.

## Batch-conversion correction in 0.7.26

On Windows, Qt enum user data may be returned as plain strings. After manual batch configuration this previously caused `'str' object has no attribute 'value'`. The import plan now normalizes classification, duplicate-depth policy, active index, NULL, and language immediately. This is unrelated to a 0.4/0.2 m step: LAS accepts the actual `STEP=0.4`; a 0.2 m grid is created only by explicit resampling. Batch errors now also identify the failing stage: reading, analysis, planning, import, writing, or LAS reopen validation.

## Responsive dialog and safe close

Binary block reading, analysis and Dataset creation run in worker threads. Channel, preview and diagnostics tables are populated in short Qt timer slices, allowing repaint, close and cancellation events to continue. Expensive `ResizeToContents` work is disabled during population.

The header shows the current file, one of six stages, overall percentage, processed count and elapsed time. The footer always keeps Cancel/Close, Save LAS and Open in editor visible. Closing during an operation requests cancellation and waits for a safe read boundary; the source DB is never modified.

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

## Standard and actual depth step

The confirmed nominal GeoScape server grid is **0.2 m**. The importer displays it separately from the actual step of the selected depth channel. The supplied `BLData.db` contains rows predominantly at **0.4 m**, which indicates that this particular file was probably recorded with a different server setting.

The LAS `STEP` header always describes the data grid that actually exists. The importer therefore never writes a false `STEP=0.2` for 0.4 m rows. To create a derived 0.2 m grid, open the document and explicitly run **LAS Editor → Resample depth…**, then choose the interpolation method. The source DB and the original imported dataset remain unchanged.

## LAS and TIME → DEPTH

Depth export writes the active index first as `DEPT.M`; `STRT`, `STOP`, and a median positive `STEP` are derived from data. Time export writes `TIME.SEC`, stores the initial date/time in the header, and retains depth as `DEPTH.M`.

**Convert time data to depth** creates a new derived dataset without modifying the source. Methods are first, last, mean, median, minimum, maximum, nearest, and explicit linear interpolation. Missing bins are not aggressively filled unless linear interpolation is selected.

## Batch conversion

**Tools → Batch DB → LAS conversion** accepts files or directories, recursive search, a profile, depth/time output, `{source_name}_{mode}.las` naming, skip/overwrite protection, progress, cancellation, and a JSON log next to the result. An ambiguous file without a matching profile receives a **Configuration required** status. Select the row, click **Configure selected DB…**, assign depth/time in the standard import dialog, and apply the plan to the batch operation. The plan is retained for the current session and only that file can be retried.

## Verified samples and limitations

The supplied samples verify Paradox 7.x `NUMBER` and `LONG`: `BLData.db` has 3488 rows/70 fields and `D250.db` has 1739/101. The implementation also contains bounded best-effort decoding for Alpha, Date, Short, Logical, Time, Timestamp, AutoIncrement, BCD, and Bytes/Blob, but those types were not present in the supplied samples and require additional real-world validation. A field-level decode error is logged and must not crash the application.
