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

This layer is only an inventory and preflight check. Semantic mapping and atomic `Dataset`
creation are handled by the separate [data-import workflow](WITSML_DATA_IMPORT.md).

## Security boundary

ZIP/EPC content is never extracted to the file system. XML is read in chunks directly from a
file or archive member; a complete payload is not loaded before preflight validation. Parsing
stops immediately when byte size, nesting depth, element count, aggregate text, attribute count,
attribute bytes, or per-element attributes exceed their limits. DTDs, entities, external entities,
and notations are rejected by streaming parser callbacks rather than by scanning only a prefix.

Traversal paths, case-insensitive duplicate names, encrypted members, total uncompressed size,
and suspicious compression ratios are also checked. Limits are configurable through
`WitsmlInventoryLimits`. Defaults are intended for offline metadata inventory, not unlimited
loading of large time-series arrays.

## Current limitations

- official XSD validation is not yet performed;
- WITSML 1.x and channel data arrays are not parsed by this metadata-only command;
- inventory performs no network requests and uses no credentials;
- an `.epc` or `.zip` extension alone never makes package content trusted.

## Related workflows

Use [offline data import](WITSML_DATA_IMPORT.md) for bulk ChannelSet data and
[read-only SOAP](WITSML_1411_SOAP.md) for WITSML 1.4.1.1. ETP 1.2 has a separate foundation,
while production interoperability and the long-running field gate remain open in the
[single project plan](../PROJECT_PLAN.md).
