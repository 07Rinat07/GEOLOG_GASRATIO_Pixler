# GEOLOG GASRATIO@Pixler 0.7.75 — WITS0 Import Review and immutable AcquisitionDatasetSchema

## WITS0 Import Review

- Added a Qt-independent `Wits0DiscoveryAccumulator` that collects every data `record/item`, type, UOM, valid/NULL/error counts, numeric range, and bounded samples.
- The discovery snapshot is immutable and deterministic for live/replay. Its fingerprint describes the mapping surface, so additional values for existing fields do not make a confirmed schema stale.
- A new or changed `record/item`, inferred value kind/UOM, or newly available header datetime changes the fingerprint and marks the schema stale.
- `Wits0ImportReviewController` separates draft, preview, and atomic commit; raw bytes, parser output, and the project are not mutated during review.
- The new dialog shows all detected fields together with blocking and advisory QC findings.

## Semantic mapping, UOM, and index

- Automatic mapping proposals use the existing Semantic Channel Dictionary.
- Every channel can confirm or override canonical mnemonic, semantic kind, quantity class, source UOM, and canonical UOM, or be excluded.
- Active-index candidates are produced from WITS header date+time and suitable numeric time/depth fields.
- The selected index field is not duplicated as a Dataset curve.
- Non-numeric channels, incompatible quantity classes, and required numerical UOM conversion block commit.
- Unknown record/items remain visible for manual mapping instead of being silently discarded.

## Immutable schema and versioned custom profile

- A successful confirmation atomically creates the existing immutable `AcquisitionDatasetSchema` with `AcquisitionIndexSchema`, `AcquisitionCurveSchema`, `CurveMetadata`, and semantic provenance.
- The schema receives a stable SHA-256 digest for audit and the later `AcquisitionSession` boundary.
- User mapping is saved as a separate `<profile-id>.vN.json` file using exclusive-create; the built-in `geoscape-gswits.json` is never modified.
- A previous profile can seed the next revision; profile ID/version is validated against the base profile.
- The capture window adds **Import Review…**, **Reset discovery**, discovered-channel count, schema state, digest, and the saved versioned-profile path.

## Limitations and next increment

- Stage C does not perform numerical conversion between compatible units; source and canonical UOM must resolve to the same canonical unit.
- Confirmation does not yet start an `AcquisitionSession` or append Dataset rows.
- The built-in GeoScape mapping still requires comparison with a real anonymized GSWITS raw stream.
- Next is stage D: WITS frame → normalized measurement batch → append-only `AcquisitionSession` through `AcquisitionController`, with checkpoints, a bounded queue, and backpressure.

## Compatibility

Project format remains `v20`, form schema `v8`, and tablet layout `v18`; no project migration is required. All ready and user forms, **Create form**, **Save user form**, duplicate and whitespace name protection, compact columns `50%`, `48`, and `80`, **Ctrl+S**, and reopen behavior are unchanged.
