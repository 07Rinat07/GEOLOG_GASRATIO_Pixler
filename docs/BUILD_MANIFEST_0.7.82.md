# Build manifest — GEOLOG GASRATIO@Pixler 0.7.82

## Package

- Package version: `0.7.82`
- Python: `>=3.11`
- Project format: `v20`
- Form schema: `v8`
- Tablet layout: `v18`

## Increment

- URI-stable ETP ChannelMetadata discovery;
- Semantic Channel/UOM Import Review;
- normalized ChannelData measurement batches;
- append-only ETP AcquisitionSession through AcquisitionController;
- bounded queue, atomic enqueue, backpressure, checkpoints and controlled close;
- exact reconnect-overlap deduplication;
- persisted recent point-hash restoration;
- desktop controls for review, start, flush, close and open-session restore.

## Validation

- targeted headless gate: `222 passed, 2 skipped`;
- project save/reopen and overlap-window restoration covered;
- `compileall` passed for `src`, `tests`, `tools`, and `scripts`;
- full collection discovered `1328 tests` and stopped with `83` missing PySide6/pyqtgraph collection errors;
- documentation audit: `114` localized Markdown files per language;
- localization catalogs: `2224` synchronized keys for RU/KK/EN;
- wheel built with local build isolation disabled, ZIP integrity passed;
- isolated `--no-deps` wheel install and headless imports passed.

Real ETP Avro/WebSocket interoperability and Windows Qt runtime testing remain external acceptance gates.

## Artifacts

- Source archive: `GEOLOG_GASRATIO_Pixler_0.7.82_ETP12_Acquisition.zip`
- Wheel: `geolog_gasratio_pixler-0.7.82-py3-none-any.whl`
- Integration plan: `GEOLOG_GASRATIO_Pixler_WITS_Integration_Plan_0.7.82.md`
- ETP gate: `GEOLOG_GASRATIO_Pixler_ETP12_Interoperability_Gate_0.7.82.md`
- Smoke report: `GEOLOG_GASRATIO_Pixler_ETP12_Acquisition_Smoke_0.7.82.json`
