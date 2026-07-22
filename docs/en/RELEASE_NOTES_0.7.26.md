# Release notes 0.7.26 — typed DB → LAS import-plan hotfix

## Fixed failure

On Windows, `QComboBox.currentData()` may return a `StrEnum` value as a plain string. A manual plan created from the batch converter could therefore reach the importer with string values such as `classification="time_with_depth"` or `duplicate_depth_policy="keep_all"`. Metadata serialization then accessed `.value` and the operation failed with:

```text
'str' object has no attribute 'value'
```

`ParadoxImportPlan` is now the single typed boundary. Construction now:

- converts Qt/JSON strings into `DatasetClassification` and `DuplicateDepthPolicy`;
- validates `active_role`, NULL, language, index fields, and channel mappings;
- rejects unsupported values before reading or export starts;
- guarantees that the internal importer receives a normalized plan.

The manual configuration dialog also performs explicit Qt-value conversion before creating the plan.

## Batch diagnostics

Batch errors now include the failing stage:

- DB reading;
- channel analysis;
- import-plan preparation;
- dataset creation;
- LAS writing;
- LAS reopen validation.

This replaces an unexplained internal exception with a file-specific operation stage.

## 0.4 m source step versus the 0.2 m standard

The `.value` failure is unrelated to the depth step. LAS 2.0 does not require a 0.2 m step. If source rows are actually stored at 0.4 m, the exported `STEP` must remain 0.4 m. The GeoScape 0.2 m server standard is stored separately as metadata.

A 0.2 m grid must be created explicitly in the LAS editor with a selected interpolation method. The batch converter does not silently invent intermediate rows or replace the actual `STEP`.

## Compatibility

- source DB/PX/TV/FAM files remain read-only;
- project and annotation schemas are unchanged;
- profiles from 0.7.16–0.7.25 remain loadable;
- string values from old and new profiles are normalized consistently;
- this remains a test build until a real Windows `DB → LAS → reopen` run is completed.
