# Project plan

Current on 27 July 2026 after the 0.7.79 slice. This file contains unfinished work only; implemented
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

## Next product increment: WITSML 1.4.1.1 SOAP read-only

- [ ] implement GetVersion/GetCap and read-only Well → Wellbore → Log → LogData;
- [ ] keep credentials outside project files;
- [ ] add timeout/retry/audit without Add/Update/Delete.

## GeoScape II GS2 acceptance

- [ ] add versioned projections and anonymized fixtures from other GeoScape releases;
- [ ] test damaged, truncated and multipart tables with golden fixtures;
- [ ] compare SG-8 and at least two other containers with reference LAS/Excel exports;
- [ ] confirm C1–C5, total gas, TIME/DEPTH, units and file segmentation.

## Acceptance criterion

One real GSWITS stream must survive reconnect, view pause, project save, crash restart and low-space
boundary while raw bytes, connection journal, recovery manifest, acquisition session, checkpoints
and Dataset projection remain consistent.
