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

Multipart tables are offered as one series only when the base part and every contiguous suffix
exist, all field names/types/sizes match, and a TIME field is present. Individual fragments of a
valid group are hidden from normal selection, preventing an accidental partial import. The merger
normalizes supported TIME representations to seconds for validation, rejects non-monotonic parts
and overlaps, reports large inter-part gaps as QC warnings, checks decoded-memory limits,
preallocates the final arrays once, and preserves monotonic progress/cancellation during both
extraction and reading. The СГ-8 series combines five parts into 4,338,103 rows.

## Access metadata implemented

The importer extracts only `GS2.mdb` into an automatically removed directory and opens that copy
read-only through the PySide6 Qt SQL ODBC adapter. Microsoft Access Database Engine must match the
application bitness. Missing QODBC/ACE, a bitness mismatch, and open failures are warnings with a
specific remedy; they never block a valid Paradox table.

For the supplied СГ-8 container, the database is a 10,670,080-byte Jet 4 database with 103 user
tables. The implemented projection reads `WELLS`, `FORMULAS`, `LOGGINGSERVICE`, explicit
channel-like tables when present, and inventories all table names:

- `WELLS` identifies well 224, СГ-8, Kazakhstan, the Karaton field and Karaton Subsalt area;
- `Гелиос` is `STATIONMODEL`, not a company;
- `FORMULAS` has 24 rows, including 17 rows with `RESGID`;
- the proven relation is `FORMULAS.RESGID=N -> Paradox field SN`;
- 13 such formula outputs exist in `GS2#101.db`, including `S1009`, `S204`, `S820`, `S1004`,
  `S1015`–`S1017`, and `S600`.

This particular MDB contains neither channel-unit columns nor formal Access relationships linking
rows to `GS2#*.db`. `RESGID` is a channel identifier and must not be treated as the number in
`GS2#101`. Formula rows without `RESGID` are not guessed. Confirmed formula names are combined
with the existing Sensors `legacy_gid` catalog for canonical mnemonics and units; unresolved
`Sxxx` and `SBxxxx` fields remain unchanged. Applied Access relations are retained in curve
semantic evidence/provenance, while the well passport, formula snapshot, channel relations, and
driver diagnostics are stored in `Dataset.parameters`.

The main `GS2#1…GS2#1_4` TIME series has no direct output-name relation in `FORMULAS`, so its
eight S-codes use Sensors where a deterministic legacy mapping exists and otherwise remain raw.
Supporting another GeoScape Access schema requires a new projection, not changes to the container
or Paradox readers.

## Index and resampling invariant

The importer preserves source values and the actual TIME/DEPTH index. It estimates the regular
step robustly so isolated gaps do not turn a 0.2 m source into a reported 0.4 m source. Conversion
to the 0.2 m project grid is a separate derived operation and never mutates the imported dataset.

## Completion gate

GS2 support is complete when tests reproduce the reference index and selected channels from at
least three representative containers, including the СГ-8 sample, and cover multipart arrays,
NULL, cancellation, corruption, cleanup, C1–C5, total gas, and LAS export. The remaining acceptance
work is versioned/golden Access fixtures and comparison with authoritative GeoScape LAS/Excel
exports; the СГ-8 MDB cannot supply units that it does not contain.
