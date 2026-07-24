# Import Review

## Purpose

Import Review is the mandatory shared stage before CSV/TXT, Excel, LAS, or
GeoScape/Paradox data is attached to a project. The format adapter first creates a temporary
`Dataset`; the user then reviews its index, channel semantics, units, NULL handling, and QC.
Only an accepted copy reaches `ProjectSession`.

## Workflow

1. Select the source and complete the format-specific options.
2. Let the adapter parse the file into a temporary domain model.
3. Review the active index and channel table.
4. Apply mapping, UOM, or additional NULL-sentinel overrides when required.
5. Resolve blocking errors and choose **Accept import**.

Cancelling the dialog creates no well or dataset and does not change the project dirty state.

## Index and NULL handling

The dialog can select any index already present in the temporary dataset and edit its mnemonic,
role, type, and unit. Valid role/type pairs are:

- `depth` with MD, TVD, or TVDSS;
- `time` with relative time or datetime;
- `generic` with a generic index.

An additional numeric NULL sentinel such as `-999.25` is replaced with `NaN` only in the
accepted copy. The source file and loader-owned temporary dataset remain unchanged.

## Manual channel mapping

Each channel can be enabled or excluded, and the user can edit its canonical mnemonic,
canonical kind, quantity class, and UOM, or restore the automatic Semantic Channel Dictionary
result.

Changing UOM in Import Review does not convert values. It only corrects metadata and is recorded
in `SemanticChannelBinding.evidence`. A manual physical-semantic change uses
`matched_by=manual_import_review` with confidence `1.0`.

## QC and acceptance rules

The preview reports valid and NULL index values, duplicates, gaps, mixed/descending order,
unresolved semantic channels, missing or unknown UOM, UOM/quantity conflicts, all-NULL
channels, and duplicate canonical kinds.

Index errors, UOM/quantity conflicts, and a plan with no enabled channels block acceptance.
Warnings remain visible and may be accepted deliberately.

## Atomic boundary

`ImportReviewController.preview()` and `commit()` operate on deep copies. `commit()` returns a
new dataset only after validation, and `DatasetImportJobExecutor` registers that copy through
one project-session port call. Cancellation, validation failure, or window close therefore
cannot leave partial project data.

Accepted datasets record `IMPORT_REVIEW_VERSION=1` and `IMPORT_REVIEW_ACCEPTED=true`; an
additional sentinel is recorded as `IMPORT_REVIEW_NULL_VALUE`.

## Compatibility

- current project format v20 remains unchanged;
- LAS/CSV/Excel/DB sources remain read-only;
- the lossless LAS document and import report remain separate from the reviewed copy;
- LAS batch import opens one review per file;
- unit edits never perform implicit value conversion.

## Diagnostics and recovery

Since 0.7.46, warnings remain non-blocking while failures are collected by read, parse, policy,
review, registration, and presentation stage. The report dialog shows a stable code, severity,
source, corrective action, and traceback and supports Copy/Save. If registration succeeded but
the tablet could not render, the application opens a safe LAS table without removing the imported
data. Duplicate vendor mnemonics are read by physical column and one malformed channel is skipped
with a warning instead of rejecting the whole source.
## Repairable mixed DB order

Since 0.7.47, a mixed numeric index can be repaired with “Sort the accepted copy by the active
index”. GeoScape/Paradox enables the recommendation automatically. All indexes, depth values,
and curves use one stable permutation; the source DB and loader-owned dataset remain unchanged.
The review records `index-sorted-copy`, while duplicates and gaps remain explicit warnings.

