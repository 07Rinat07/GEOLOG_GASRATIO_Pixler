# GEOLOG GASRATIO@Pixler 0.7.82 — ETP ChannelData AcquisitionSession

This release completes stage I.1:

- URI-based ETP channel discovery that survives numeric channel-ID changes;
- Semantic Channel/UOM Import Review and immutable AcquisitionDatasetSchema;
- ChannelData grouping by canonical time/depth index;
- explicit scalar UOM conversion and ETP microsecond-to-Unix-nanosecond normalization;
- append-only `Etp12AcquisitionRuntime` over `AcquisitionController`;
- bounded queue, atomic multi-row enqueue, backpressure, checkpoints and controlled close;
- exact reconnect overlap deduplication using stable point SHA-256 identities;
- restoration of the bounded dedup window from persisted AcquisitionRecord provenance;
- UI controls for review, start, flush and close, plus open-session restoration after metadata reload.

Project format remains v20. Real ETP Avro/WebSocket interoperability and Windows Qt testing remain
external acceptance gates.
