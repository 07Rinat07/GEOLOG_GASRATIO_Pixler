# WITSML 2.x ChannelSet data import

## Purpose and boundary

Version 0.7.79 adds an offline, read-only source parser and an atomic project-import workflow for
WITSML 2.x `Log/ChannelSet` bulk data. The parser never edits the XML, EPC/ZIP member or external
bulk-data file. The project is changed only after Import Review produces a complete immutable
`WitsmlImportCommit` containing the final `Dataset`, diagnostics and SHA-256 provenance.

Open **File → Import WITSML 2.x data…**. The existing inventory command remains a metadata-only
preflight tool and does not create a Dataset.

## Supported data representation

The importer reads a top-level `ChannelSet` or each direct `ChannelSet` inside a WITSML `Log`. A
ChannelSet must declare one or more `Index` entries, one or more `Channel` entries and optional
`ChannelData`. Bulk rows use the JSON-compatible layout:

```text
[
  [[index-1, index-2], [channel-1, channel-2, channel-3]],
  [[index-1, index-2], [channel-1, channel-2]]
]
```

A shorter index or channel array is padded with trailing null values. Embedded `Data` and safe
relative `FileUri` JSON/text payloads are supported. If both are present, `FileUri` takes
precedence. Binary Avro payloads are reported as unsupported rather than guessed.

## Safety controls

The reader rejects DTD/entity declarations, non-WITSML namespaces, unsupported schema versions,
absolute or escaping `FileUri` paths, encrypted archive members, duplicate archive paths,
suspicious compression ratios and configured file/element/row/cell limits. ZIP/EPC members are
read in memory and are never extracted to arbitrary disk paths.

Structurally valid rows are retained even when an index value is invalid. Import Review can then
count, display and explicitly drop those rows. Source bytes and source/data SHA-256 values remain
available in Dataset provenance.

## Import Review

The dialog lets the operator:

- select one ChannelSet from a Log or package;
- choose the active time or depth index;
- enable only required scalar numeric channels;
- review source mnemonic, type and UOM;
- change canonical mnemonic, quantity class and target UOM;
- enable stable index sorting;
- choose whether rows with invalid active-index values are dropped;
- review valid, null and invalid value counts before commit.

String, vector and point-metadata channels are visible but disabled by default. Enabling an
unsupported channel type creates a blocking diagnostic. Duplicate canonical mnemonics or semantic
kinds also block commit.

## UOM normalization

Numerical conversion is performed only through an explicit conversion family in the UOM
dictionary. Examples include `ft/h → m/h`, `ft → m`, pressure, volume, flow, density and electrical
units. Units that merely share a broad quantity class but have no universal conversion are not
relabelled. An unsupported or conflicting source/target UOM blocks commit.

Time indexes require timezone-aware ISO 8601 values and are normalized to UTC `datetime64[ns]`.
Numeric index values are converted through the same strict UOM service as channels.

## Atomic Dataset creation

`WitsmlImportReviewController.commit()` creates all arrays, metadata, semantic bindings, index
contract and provenance before any project mutation. `WitsmlProjectImportController.register()`
then attaches exactly that reviewed immutable commit in one project-registration boundary.
Parsing, validation or registration failure restores the previous current well, current Dataset
and dirty state.

The Dataset records:

- source file/member and WITSML schema version;
- ChannelSet UUID/key and selected index key;
- source XML and data SHA-256 values;
- source/imported/skipped row counts;
- the `[[indexes],[channels]]` layout identifier;
- a deterministic Dataset digest.

## Current exclusions

Offline import handles scalar numeric data only; Binary Avro and multidimensional channel arrays
are unsupported. WITSML 1.4.1.1 read-only SOAP and the ETP 1.2 foundation are separate implemented
paths, while production ETP interoperability and the Windows WITS0 field-reliability gate remain
open.
