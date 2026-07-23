# Semantic Channel Dictionary

## Purpose

The dictionary gives LAS, CSV/TXT/Excel, and GeoScape/Paradox channels one engineering meaning.
It does not silently rename source data or guess an unknown unit. The resolved decision is stored
with the curve so a later catalog update cannot change the meaning of an existing project.

## Rule sources

- the Sensors catalog provides canonical mnemonics, vendor aliases, legacy `S/GID`, sensor IDs,
  family, category, and reference UOM;
- `UomDictionary` provides explicit UOM aliases and quantity classes;
- `SemanticChannelDictionary` combines the evidence into a stable definition and binding.

The Sensors catalog remains the single source of vendor aliases.

## Per-curve binding

`SemanticChannelBinding` stores:

- canonical kind and canonical mnemonic;
- quantity class;
- canonical UOM and original source UOM;
- aliases, sensor ID, source, family, and category;
- the exact source mnemonic;
- confidence, match method, and evidence.

Project format v16 persists the binding in curve metadata. A legacy curve is enriched while it is
read, without replacing an already stored canonical mnemonic.

## UOM policy

Only explicit aliases are normalized. Every known UOM belongs to a quantity class such as length,
time, pressure, volume fraction, flow rate, density, or temperature. An unknown string remains
unknown; no conversion or physical assumption is made silently. A physical mismatch between the
channel meaning and source UOM lowers confidence and becomes a `channel-uom-conflict` review error.

## Integration and Import Review

CSV/Excel, LAS, and Paradox imports create the same binding. Copy, transfer, merge,
reverse/resample, TIME↔DEPTH, aggregation, and dataset JSON export preserve it.

`build_import_review(dataset)` returns a deterministic read-only model with index details,
semantic bindings, valid/NULL counts, unresolved channels, missing/unknown UOM, quantity
conflicts, all-null channels, and duplicate canonical kinds. It never mutates the dataset.
The interactive screen, manual overrides, and atomic acceptance command are the next slice.
