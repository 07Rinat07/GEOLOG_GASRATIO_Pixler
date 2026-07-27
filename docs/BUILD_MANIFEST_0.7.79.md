# Build manifest — GEOLOG GASRATIO@Pixler 0.7.79

## Release identity

- Package version: `0.7.79`
- Project format: `v20`
- Form schema: `v8`
- Tablet layout: `v18`
- Main increment: offline WITSML 2.x ChannelSet/Channel data arrays, index/channel selection,
  strict UOM normalization, Import Review and atomic Dataset registration.
- Compatibility: no project/form/tablet schema migration.

## Implemented WITSML boundary

- Safe XML/directory/ZIP/EPC ChannelSet discovery with resource and traversal limits.
- Embedded JSON-compatible `ChannelData.Data` and safe relative text/JSON `FileUri` support.
- Official `[[index values], [channel values]]` row layout with trailing-null completion.
- Time/depth index selection, invalid-index policy, stable sorting and scalar numeric channel choice.
- Semantic Channel Dictionary binding and explicit source/canonical UOM review.
- Strict numerical conversion families; unsupported conversions block commit.
- UTC datetime indexes and numeric depth indexes.
- Deterministic source/data/Dataset SHA-256 provenance.
- Atomic registration of the exact immutable dialog commit with rollback on project failure.

## Validation performed in the release container

- Targeted headless integration gate: **140 passed, 5 skipped**.
- WITSML data/import/project tests cover embedded data, relative EPC files, invalid-index policy,
  UTC time indexes, secondary index selection, UOM conversion, deterministic digests and project
  rollback.
- Documentation audit: **107 localized Markdown files per language**, **2127 synchronized RU/KK/EN keys**.
- Python bytecode compilation: `src`, `tests`, `tools`, `scripts` completed successfully.
- Wheel ZIP integrity, required-module inspection, isolated no-dependency installation and headless
  smoke imports passed.
- The broader Qt localization/full GUI suite was not collected successfully because `PySide6` and
  `pyqtgraph` are unavailable in this Linux container. A full Windows Qt result is not claimed.
- The real-GSWITS Windows field gate is not claimed by this release.

## Wheel

- File: `geolog_gasratio_pixler-0.7.79-py3-none-any.whl`
- Size: `3018944` bytes
- SHA-256: `7798fd75a61d9b304c963936dd50c479c7738e066faff92613333875b0a8325b`
- ZIP integrity: passed.
- Isolated no-dependency installation and headless WITSML/UOM smoke import: passed.

## Parallel Windows field gate

The real 8–24 hour WITS0 reliability gate remains open. See
[WITS0_WINDOWS_FIELD_GATE.md](WITS0_WINDOWS_FIELD_GATE.md). The source-archive hash is reported in
the external handoff to avoid recursive hashing.
