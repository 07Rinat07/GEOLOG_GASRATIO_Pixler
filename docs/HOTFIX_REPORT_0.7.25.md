# Hotfix report 0.7.25

## Confirmed regressions

1. The batch converter stopped at ambiguous DB indexes and offered only an error message.
2. The annotation implementation used a full-size translucent child widget above PyQtGraph. On Windows this could be composited as a solid black rectangle.

## Implemented correction

### Batch conversion

`BatchStatus.CONFIGURATION_REQUIRED` separates manual configuration from failures. The batch dialog stores per-source `ParadoxImportPlan` objects for the current session. `ParadoxImportDialog(configuration_only=True)` returns a validated plan without importing or opening a document. The user can configure the selected DB and retry it immediately.

### Tablet rendering

The full-size painting overlay and all `QRegion/setMask/WA_TranslucentBackground` logic were removed. The manager widget is hidden and has an empty `paintEvent`. Each annotation is rasterized into a transparent pixmap and displayed by a small mouse-transparent label clipped to the graph body. With no visible annotations there are no visible overlay widgets at all.

## Compatibility

- project and annotation schemas are unchanged;
- old annotations remain readable;
- the Paradox reader remains read-only;
- normal track editing and the OOP input router are retained;
- PDF/print paths still use the same annotation model through `paint_translated`.

## Environment limitation

PySide6, pyqtgraph and lasio are unavailable in the build container. Therefore Windows GUI composition and complete DB → LAS → reopen verification must be performed in the target environment before promotion from TEST to stable.

## Validation result

- Python compilation: passed;
- focused dependency-free suite: 140 passed;
- RU/KK/EN catalogs: 1559 identical keys with placeholder parity;
- JSON: 22 files valid;
- `BLData(1).db`: 3488 rows and 70 imported channels, no skipped rows/channels;
- `D250(1).db`: 1739 rows and 101 imported channels with explicit manual index plan, no skipped rows/channels;
- source hashes unchanged;
- Windows GUI and lasio round-trip: not run in this container.
