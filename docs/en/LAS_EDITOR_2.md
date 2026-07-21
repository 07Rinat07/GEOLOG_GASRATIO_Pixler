# LAS Editor 2 — safe merging, external LAS insertion, and batch editing

Updated: 21 July 2026

## Purpose

LAS Editor 2 combines depth normalization, progressive LAS merging, direct insertion of
external curves, mouse-based curve editing, spreadsheet operations, and exports.

Source LAS files on disk are never overwritten automatically. Transformations create a new
project copy or modify only the current working dataset. Disk output is explicit through LAS
export or project save.

## Ascending-depth copy

**Create ascending-depth copy** handles LAS files whose depth runs from high to low. The new
copy reverses the active depth index, every curve, additional indexes, and STRT/STOP/STEP
consistently. The original dataset and source file remain unchanged.

## Progressive depth merge

**Merge datasets by depth…** creates a new derived copy from two previously imported LAS
files. Overlap policies are:

1. Preserve the old LAS and fill missing values from the new LAS.
2. Prefer the new LAS on overlap.
3. Keep both curve versions separately.

Curves, additional indexes, headers, and parameters are retained. Incompatible duplicate
mnemonics are preserved under a unique name. `MERGE_MANIFEST` records parents, policy, header
conflicts, and overlap differences. Missing samples are not interpolated.

## Insert data from an external LAS

**Insert data from external LAS…** reads a disk file and adds selected curves to the current
dataset. It is intended for wireline data, directional surveys, well trajectory channels,
laboratory measurements, and third-party engineering curves.

- identical depth grids are copied without interpolation;
- partial overlap is interpolated only inside the common interval;
- `NULL/NaN` samples and large gaps are never bridged;
- values outside the overlap remain missing;
- depth units `m`, `ft`, `cm`, and `mm` are converted to the current LAS depth unit;
- a descending external source is reversed only in a temporary in-memory copy;
- the external file is not modified.

An `EXTERNAL_LAS_IMPORT_*` manifest stores source SHA-256, path, encoding, mapping details,
and inserted curves. Undo is available until an inserted curve receives later edits.

The physical source unit is preserved. Display names and display units for forms/PDF are
edited at track-binding level; changing a caption does not convert numeric values.

## Pencil editing

Open one source curve, enable **Pencil** or press `E`, hold the left mouse button, and draw the
replacement segment. Samples are snapped to the depth index and committed as one Undo/Redo
command. Existing dependent Gas Ratio outputs, `TG_CALC`, Pixler profiles, and recorded custom
formulas are recalculated synchronously. Calculated curves remain read-only.

## Excel-like LAS table

The table supports rectangular and sparse selection, `Ctrl+C`, `Ctrl+V` from Excel, one-value
fill over multiple selected cells, blank cells as `NaN`, `Delete`, range operations, atomic
Undo/Redo, and synchronous dependent recalculation. Depth and calculated columns are read-only.

## Export

Selected cells or all parameters can be exported to Excel `.xlsx`, TSV `.txt`, or CSV `.csv`.
Exports include depth, selected curves, units, and values and do not modify the LAS source.

## Graphical curve editing with the pencil

1. Open a LAS dataset and press **Curve pencil** on the main toolbar or press `E`.
2. Select a source parameter from the dialog. Calculated curves are excluded from direct editing.
3. The application switches to the single-curve graph. The **Editable curve** selector and mode status are shown above the plot.
4. Hold the left mouse button and draw the required curve shape. An orange preview line follows the pointer.
5. Releasing the button snaps the edit to real depth samples and records it as one Undo/Redo command.
6. Dependent calculated parameters are recalculated synchronously. Save the project with the diskette button or `Ctrl+S`; export an updated LAS separately when required.

The pencil can also be started from the tablet: right-click a graphical track or a specific curve caption and choose **Edit curve with pencil…**.
