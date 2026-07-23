# Release notes 0.7.32 — Semantic Channel Dictionary

## Changes

- added one `SemanticChannelDictionary` and `UomDictionary` on top of the existing Sensors catalog;
- every imported curve receives a serializable binding with canonical kind, quantity class, UOM,
  aliases, sensor/source, source mnemonic, confidence, and evidence;
- CSV/Excel, LAS, and Paradox use the same resolver;
- unknown vendor channels and units remain explicit rather than being guessed;
- a UOM quantity conflict lowers confidence and is exposed as a review error;
- copy, transfer, merge, reverse/resample, and TIME↔DEPTH preserve the semantic snapshot;
- added a read-only headless Import Review model for index, NULL, unresolved channels, UOM, and
  duplicate canonical kinds;
- Curve Catalog and dataset JSON export consume the stored semantics;
- raised project format to v16 with a safe v15 → v16 migration.

## Compatibility

Legacy projects open without data loss. A missing binding is reconstructed while reading without
replacing an already stored canonical mnemonic. Source LAS/DB files remain unchanged, and this
slice does not alter layouts or user workflows.

## Verification

707 available tests passed and 4 platform-specific scenarios were skipped; `compileall` and the
0.7.32 wheel build completed successfully. The full Qt/LAS pytest, Ruff, mypy, and
Windows/HiDPI/PDF/physical-print gate must be repeated in an installed environment.
