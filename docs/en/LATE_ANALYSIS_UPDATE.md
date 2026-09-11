# Importing late cuttings analyses

Late laboratory calcimetry, LBA, and interpretation results can be added safely to already saved cuttings samples without re-importing the source LAS.

## Before you start

- Open the required `.geologpkg` and select the well.
- The project must already be saved to disk because confirmed changes are material-autosaved immediately.
- The source analysis file is never modified.

## Supported files

The command accepts `CSV`, `TXT`, `XLSX`, and `XLSM`. CSV/TXT supports UTF-8 and CP1251 and detects the delimiter automatically. Excel import reads the first worksheet.

Top and bottom interval depths are required. A sample ID and supported LBA, calcite, dolomite, and interpretation fields are optional. A blank value means that no new result is supplied and never clears an existing project value. One import is limited to 10,000 data rows.

## Workflow

1. Open **File → Import late analyses…**.
2. Select the laboratory result file.
3. The application matches source rows to existing cuttings intervals and builds a preview.
4. Review matches, missing values, and conflicts. Existing populated values are protected from overwrite.
5. Select only the empty fields that should be filled.
6. Confirm the update.

Re-importing the same values is a safe no-op: it creates no unnecessary well revision and does not trigger another project save.

## Persistence and failure handling

After confirmation, the selected fill-only diff is applied to the active well and the project is then persisted through the normal `MATERIAL_AUTOSAVE` path. `analysis_update_history` records the source, file SHA-256, selected fields, exact diff, and before/after state hashes.

If project persistence fails, the operation is treated as unsuccessful: cuttings values, analysis history, the well revision, and the previous session `dirty` state are restored. A success message is shown only after the project has been written successfully.

## Current increment limitations

- Legacy binary `.xls` is not supported; save it as `.xlsx` first.
- Excel import uses the first worksheet.
- This command updates analyses of existing samples only and does not transfer user drawings.
- Conflicting numeric rock codes from different suppliers belong to PROJ-09 profiles and are not resolved automatically by this command.
