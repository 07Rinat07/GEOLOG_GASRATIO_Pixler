# WITSML 2.x inventory

## Purpose

The inventory performs a safe, read-only inspection of local WITSML 2.x data before project
import. It shows top-level objects, schema versions, UUIDs, object references, and channel
metadata. The operation does not create a `Dataset`, modify the project, or connect to a server.

Open **File → WITSML 2.x inventory…**. A supported file can also be dragged into the main window.

## Supported sources

- one `.xml` or `.witsml` file;
- a directory scanned recursively for XML/WITSML files;
- an `.epc` or `.zip` package read in memory without extracting members to disk.

Only top-level objects using a WITSML 2.x namespace are recognized. `schemaVersion` must belong to
the 2.x line. An invalid object inside a mixed package becomes a diagnostic while valid objects
remain available for review.

A synthetic manual-test fixture is included at `resources/samples/witsml/channel_2_1.xml`.

## Object and channel data

Each object row shows the source member, XML type, `schemaVersion`, `Citation` title, UUID/uid,
`GrowingStatus`, and the number of detected references. A `Channel` additionally shows:

- `Mnemonic`, `DataType`, `Uom`, `Source`, `LoggingMethod`, and channel class;
- every direct `Index`, including type, mnemonic, unit, direction, and datum reference;
- `StartIndex` and `EndIndex`.

This layer is an inventory and preflight check. Semantic channel mapping, acquisition-schema
creation, and appending rows to a `Dataset` remain a separate atomic workflow.

## Security boundary

ZIP/EPC content is never extracted to the file system. The reader rejects traversal paths,
case-insensitive duplicate names, encrypted members, oversized entries, excessive total
uncompressed size, suspicious compression ratios, and excessive XML element counts. DTD and
custom XML entities are forbidden. Single files and directories use the same size and element
limits.

Limits are configurable through `WitsmlInventoryLimits`. Defaults are intended for offline
metadata inventory, not unlimited loading of large time-series arrays.

## Current limitations

- official XSD validation is not yet performed;
- WITSML 1.x is not supported;
- channel data arrays are not imported;
- ETP 1.2, authentication, TLS, and network secrets are not implemented;
- an `.epc` or `.zip` extension alone never makes package content trusted.

## Next increment

The next increment will transform selected `Channel` objects and indexes into a proposed
`AcquisitionDatasetSchema`, present mapping/QC for review, and only then create a growing dataset
atomically. A network ETP client follows after the offline mapping and replay contract is complete.
