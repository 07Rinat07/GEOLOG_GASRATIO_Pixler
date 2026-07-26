# GeoScape II GS2 import

## Current contract

`.gs2` is treated as an immutable GeoScape II ZIP container, not as Paradox DB. The first
implementation slice:

- identifies the container by ZIP signature rather than extension alone;
- requires exactly one `GS2.mdb` and at least one `GS2#*.db`;
- rejects unsafe paths, case-insensitive duplicate names, encrypted members, excessive member
  counts/sizes, and suspicious compression ratios;
- extracts only into an automatically removed temporary directory;
- exposes table selection through universal import, the File menu, and drag-and-drop.

The СГ-8 sample proves that every `GS2#*.db` member is a Paradox 7.x table. The importer lists
their record/field counts and TIME/DEPTH roles, defaults to the richest depth table, extracts only
the selected member, and sends it through the existing Paradox mapping dialog and Import Review.
The resulting `Dataset` retains the original `.gs2` source path and selected table provenance.

## СГ-8 evidence

The supplied `Скважина СГ-8 22.07.2026.gs2` is a valid 82,903,239-byte ZIP with 14 members and
349,683,712 uncompressed bytes. CRC validation passes for every member.

- `GS2#101.db`: 10,001 rows, TIME + DEPTH + 206 channels; DEPTH 3000–5000 m at 0.2 m.
- `GS2#113.db`, `GS2#114.db`, `GS2#115.db`: 10,000-row depth tables with 7, 25, and 6 fields.
- `GS2#1.db` through `GS2#1_4.db`: one Paradox schema with four 1,000,000-row parts and one
  338,103-row part. Decoded TIME bounds are continuous from 2025-08-04 04:21:39 to
  2025-09-23 09:42:51.
- Sparse `GS2#5.db`, `GS2#10.db`, and `GS2#20.db` legitimately compress above 500:1; zip-bomb
  protection therefore combines a 1000:1 ratio ceiling with absolute per-member and total limits.

## Required architecture

```text
Gs2ContainerImporter
  -> safe temporary extraction
  -> AccessMetadataReader (GS2.mdb)
  -> existing Paradox reader (GS2#*.db tables)
  -> TIME/DEPTH reconstruction and QC
  -> Dataset + provenance
  -> Import Review
```

The Access adapter must be replaceable. The primary Windows implementation may use Microsoft
Access Database Engine/ODBC, while missing-driver and bitness mismatch cases must produce
actionable diagnostics rather than a generic import failure.

Multipart time tables must be ordered using decoded TIME bounds and metadata; filenames alone are
insufficient evidence. `GS2.mdb` remains necessary for authoritative channel names, units, and
relationships, but is no longer a blocker for importing a selected table.

## Index and resampling invariant

The importer preserves source values and the actual TIME/DEPTH index. It estimates the regular
step robustly so isolated gaps do not turn a 0.2 m source into a reported 0.4 m source. Conversion
to the 0.2 m project grid is a separate derived operation and never mutates the imported dataset.

## Completion gate

GS2 support is complete when tests reproduce the reference index and selected channels from at
least three representative containers, including the СГ-8 sample, and cover multipart arrays,
NULL, cancellation, corruption, cleanup, C1–C5, total gas, and LAS export.
