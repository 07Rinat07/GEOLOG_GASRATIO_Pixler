# Hotfix report 0.7.26

## Defect

The Windows batch workflow could pass plain strings from Qt user data into `ParadoxImportPlan`. The importer later treated `classification` and `duplicate_depth_policy` as enums and accessed `.value`, causing `'str' object has no attribute 'value'`.

## Root cause

`StrEnum` is also a subclass of `str`. PySide QVariant conversion is platform-dependent and may preserve the enum object or reduce it to its string value. The previous code assumed the enum object always survived the UI boundary.

## Correction

- `ParadoxImportPlan.__post_init__` normalizes and validates all boundary values.
- The Qt dialog explicitly constructs enum objects from `currentData()`.
- Batch failures include the current conversion stage.
- Regression tests construct plans with plain Qt-style strings and execute both direct import and batch conversion.

## Depth-step clarification

The failure is not caused by a 0.4 m source step. Actual data spacing is exported as LAS `STEP`. GeoScape's 0.2 m nominal server standard is metadata only until the user explicitly resamples the dataset.

## Validation available in this container

- targeted Paradox import and batch tests;
- real BLData/D250 read and import checks;
- Python compile checks;
- RU/KK/EN key parity and JSON validation.

PySide6, pyqtgraph, and lasio are not installed in the container, so the final Windows UI and real LAS writer round-trip remain mandatory release-gate tests.
