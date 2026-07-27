## Current increment after 0.7.83: ETP I.2

The next slice covers valueAttributes/quality, GetRanges paging and recovery, captured ETP replay,
an interoperability matrix, and Windows soak tooling. Real servers and Windows remain external gates.

## Completed in 0.7.82: ETP ChannelData acquisition

The next increment is field interoperability, channel quality attributes and server-specific paging/range recovery.

# Project plan

## Completed in 0.7.81: WITSML 2.1 / ETP 1.2

- [x] secure WebSocket session and protocol negotiation;
- [x] read-only Discovery, Store, Data Array and channel subscription;
- [x] correlation, multipart FIN, ACK and bounded reconnect;
- [x] secrets outside projects and hash-chained audit.

## Next ETP slice

- [ ] real-server interoperability matrix;
- [ ] ChannelData → normalized batches → append-only ETP AcquisitionSession;
- [ ] semantic/UOM mapping and workspace persistence;
- [ ] reconnect overlap and 8–24-hour soak.

Current on 27 July 2026 after the 0.7.80 slice. This file contains unfinished work only; implemented
increments are recorded in project status, changelog and release notes.

## Priority: WITS0 field acceptance

Raw capture, parser, Import Review, normalized batches, append-only session, live monitor and the
software reliability layer are implemented. Remaining field work:

- [ ] capture 5–10 minutes of anonymized real GSWITS raw traffic;
- [ ] confirm TCP mode, address, port, encoding, headers and record intervals;
- [ ] verify the built-in and custom GeoScape profiles against real record/item values;
- [ ] complete an 8–24 hour Windows soak with real GSWITS and retain the JSON report;
- [ ] verify reconnect after GSWITS, application and Windows restarts;
- [ ] execute a controlled low-space/disk-full test without raw loss;
- [ ] decide Windows startup/service strategy and complete a signed field checklist;
- [ ] add independent tracks/scales for incompatible units;
- [ ] define a new-source-session policy after a previous session is closed.

## Completed in 0.7.79: offline WITSML data import

- [x] select `ChannelSet`, active `Index` and scalar numeric `Channel` values;
- [x] read embedded Data and safe relative FileUri without network ETP;
- [x] bind time/depth index and Well/Wellbore metadata;
- [x] perform Semantic Channel Dictionary/UOM Import Review with numeric conversion;
- [x] atomically create and register an immutable Dataset;
- [x] include a synthetic fixture with explicit provenance and regression tests.

## Completed in 0.7.80: WITSML 1.4.1.1 SOAP read-only

- [x] GetVersion/GetCap and read-only Well → Wellbore → Log → LogCurveInfo → LogData;
- [x] timeout, bounded retry, response-size guard and hash-chained audit;
- [x] credentials outside project files through Windows Credential Manager;
- [x] reuse Import Review and atomic Dataset registration;
- [x] reject Add/Update/Delete at the client boundary.

## Next product increment: WITSML 2.1 / ETP 1.2

- [ ] select and validate an ETP 1.2 client library;
- [ ] implement session negotiation, Discovery and Channel Streaming;
- [ ] map ChannelData into the shared normalized measurement pipeline;
- [ ] add reconnect and subscription recovery with preserved provenance.

## GeoScape II GS2 acceptance

- [ ] add versioned projections and anonymized fixtures from other GeoScape releases;
- [ ] test damaged, truncated and multipart tables with golden fixtures;
- [ ] compare SG-8 and at least two other containers with reference LAS/Excel exports;
- [ ] confirm C1–C5, total gas, TIME/DEPTH, units and file segmentation.

## Acceptance criterion

One real GSWITS stream must survive reconnect, view pause, project save, crash restart and low-space
boundary while raw bytes, connection journal, recovery manifest, acquisition session, checkpoints
and Dataset projection remain consistent.
