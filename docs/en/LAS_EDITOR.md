# LAS Editor

Feature version: 0.7.6. The **Editor** section and **LAS Editor** command (`Ctrl+Alt+E`)
combine LAS creation, manual editing, depth repair, resampling, curve insertion, and file splicing.

## Source-file safety

The editor never overwrites a source LAS. Repair, resampling, insertion, and splicing create a new
independent dataset and a new `.las` file. Source path, encoding, SHA-256, and operation provenance
are retained in result metadata or a manifest.

Table edits first exist in the project's working dataset. **Ctrl+S** saves the project but does not
create a new LAS file. Export a new LAS copy when the result must be used by another application.

## Main operations

- **Create new LAS** — range, step, MD/TVD/TVDSS index, LAS 1.2/2.0, and NULL.
- **Open LAS** — import one or more files into separate working wells.
- **Edit data table** — change values, headers, and curves with Undo/Redo.
- **Repair descending depth** — reverse depth, indexes, and all curves together.
- **Change depth step** — create a copy at 0.2, 0.5, 1 m, or another positive step.
- **Insert data from LAS** — select external curves and align them by depth.
- **Splice LAS files** — combine depth sections with an explicit overlap policy.
- **Save current as new LAS** — export the working copy to a separate file.

## Vendor and legacy LAS cases

Descending depth, negative `STEP`, UTF-8, Windows-1251 and CP866, duplicate mnemonics, and
Cyrillic labels are supported. Source names remain available for diagnostics, while portable
output names are suggested: `GK:1 → GK_1` and `КС, ННК/ДСР → KS_NNK_DSR`.
The suggested mnemonic can be changed before export.

Resampling does not interpolate through NULL values or large gaps. Before acceptance, review the
range, row count, units, NULL policy, and Import Review warnings.

## Inserting curves

1. Open the target LAS.
2. Choose **Editor → Insert data from LAS**.
3. Select the external LAS.
4. Review source/output mnemonics, units, and descriptions.
5. Clear curves that are not required.
6. Select the path for the new LAS copy.
7. Click **Insert and save copy**.

A descending external file is reversed only in memory. Values are transferred to the target grid
inside the shared depth range; NULL is written outside the overlap. Source files remain unchanged.

## Splicing LAS files

1. Open both LAS files.
2. Select the target dataset in the project tree.
3. Run **Editor → Splice LAS files**.
4. Select the second dataset and overlap policy:
   - preserve current values;
   - prefer source values;
   - retain both curves under different mnemonics.
5. Choose the new output name and confirm.

Both source files remain unchanged. Check start/end depth, overlap, NULL values, units, and headers
in the created result.

## Saving and reopen verification

- **Ctrl+S** saves the working model inside the project.
- **LAS export** creates a separate portable file.
- Closing the project without saving discards table edits made after the last `Ctrl+S`.
- After important edits, save the project, export a LAS copy, and reopen both results to verify row
  count, index, and critical curves.
