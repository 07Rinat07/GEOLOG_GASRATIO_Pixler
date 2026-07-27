# GEOLOG GASRATIO@Pixler 0.7.79 — WITSML 2.x ChannelSet data import

## Offline bulk-data reader

Added safe parsing of WITSML 2.x `ChannelSet` bulk arrays from a top-level ChannelSet or direct
ChannelSets inside a `Log`. Embedded JSON-compatible `Data` and safe relative text/JSON `FileUri`
payloads are supported for XML, directory, ZIP and EPC sources. Binary Avro and multidimensional
channels remain explicit exclusions.

## Import Review and UOM normalization

The operator can select the ChannelSet, active time/depth index and scalar numeric channels, then
review or override canonical mnemonic, quantity class and target UOM. Strict linear conversion is
applied only inside a known conversion family. Invalid index rows can be counted and explicitly
dropped; invalid channel values become null/NaN with diagnostics.

## Atomic project boundary

The complete Dataset is built and hashed before project mutation. The exact immutable commit
accepted in the dialog is registered once through `WitsmlProjectImportController`; parsing,
validation or registration failure leaves the previous project selection and dirty state intact.

## Parallel field gate

The Windows WITS0 field reliability gate remains a separate parallel activity on a workstation
connected to real GSWITS. This release includes an updated acceptance checklist but does not claim
that the real 8–24 hour gate has passed.

Project format remains v20, form schema v8 and tablet layout v18.
