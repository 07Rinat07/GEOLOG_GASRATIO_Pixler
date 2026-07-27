# ETP 1.2 interoperability gate — stage I.2

This gate is evidence-driven. A server is not marked field-ready until the matrix row contains a
repeatable result, UTC timestamp, operator, sanitized evidence path, and server/version identity.
Use a read-only service account and keep credentials outside the project file.

## Matrix scope

Test at least:

- two independent ETP Store implementations;
- one Channel Streaming or Channel Subscribe producer;
- one time-indexed and one depth-indexed channel set;
- TLS certificate validation, reconnect, paging/range recovery, captured replay, and an 8–24 hour soak.

Use [ETP12_INTEROPERABILITY_MATRIX_TEMPLATE.csv](validation/ETP12_INTEROPERABILITY_MATRIX_TEMPLATE.csv)
for results. Allowed statuses are `PASS`, `FAIL`, `BLOCKED`, and `NOT_RUN`.

## Security and handshake

- [ ] WSS certificate validation succeeds without disabling verification.
- [ ] WebSocket subprotocol is exactly `etp12.energistics.org`.
- [ ] Password/token is absent from project, profile JSON, capture metadata, audit, and screenshots.
- [ ] RequestSession receives one valid OpenSession.
- [ ] Negotiated Core, Discovery, Store, Data Array, Channel Streaming/Subscribe roles match the server.
- [ ] Endpoint payload limits and compression capabilities are recorded and enforced.
- [ ] Unsupported protocol produces a controlled diagnostic without destabilizing other requests.

## Correlation, multipart, acknowledgement

- [ ] Correlation IDs match every request and response.
- [ ] Multipart response is complete only at FIN and parts are processed in message-ID order.
- [ ] ACK-requested server message receives exactly one Acknowledge with correct correlation ID.
- [ ] ProtocolException terminates only the correlated operation.
- [ ] Chunked Store/Data Array payloads are reassembled without truncation.

## Discovery, Store, and Data Array

- [ ] Discovery returns expected Well/Wellbore/Log/ChannelSet/Channel resources.
- [ ] Store returns valid WITSML 2.x XML matching an independent export.
- [ ] Data Array metadata, dimensions, logical/transport types, and values match the reference.
- [ ] Channel metadata contains stable URI, current numeric ID, index kind, UOM, data kind, and attributes.

## valueAttributes and quality

- [ ] Every `AttributeMetadataRecord.attributeId` is mapped to name, data kind, UOM, and property-kind URI.
- [ ] Known quality/status attributes produce explicit normalized quality flags.
- [ ] Unknown attributes remain in immutable provenance and are never silently discarded.
- [ ] Null, invalid, substituted, suspect, and good values remain distinguishable.
- [ ] Quality flags survive capture, replay, append-only commit, save, and reopen.

## Paging and range recovery

- [ ] `GetRanges` uses a unique request UUID and explicit channel IDs.
- [ ] Primary start/end interval, UOM, depth datum, and secondary intervals are recorded.
- [ ] Multipart `GetRangesResponse` completes only at FIN.
- [ ] Time and depth ranges are tested separately.
- [ ] Recovery resumes from the last committed index, not only the last received index.
- [ ] Exact overlap is removed downstream while changed values at the same index remain append-only.
- [ ] A gap that cannot be recovered becomes a typed operational event and visible quality marker.

## Captured ETP stream and deterministic replay

- [ ] Capture stores direction, arrival UTC, connection generation, raw Avro bytes, header summary, and SHA-256 chain.
- [ ] Credentials, Authorization headers, and decrypted TLS session secrets are absent.
- [ ] Rotation and disk-space guard do not split or lose a logical message.
- [ ] Replay uses the same decode, correlation, ACK-suppression, metadata, normalization, and dedup pipeline.
- [ ] Live and replay produce identical immutable ChannelData batches and Dataset digests.
- [ ] Truncated or tampered capture is detected before replay commit.

## Reconnect and subscription restoration

- [ ] Force network loss while subscribed.
- [ ] Session changes to FAILED/RECONNECTING without freezing UI.
- [ ] Bounded reconnect negotiates a new session and re-reads ChannelMetadata.
- [ ] Numeric channel IDs may change while URI identity remains stable.
- [ ] Active subscriptions restore from retained/committed indexes.
- [ ] Operator close stops reconnect and range recovery cleanly.

## Windows soak and evidence

- [ ] Minimum duration is 8 hours; recommended duration is 24 hours.
- [ ] Record sent/received/ACK/pending/reconnect/range/capture/dedup counters.
- [ ] Record process memory, handle count, CPU, disk free space, capture size, and Dataset rows.
- [ ] Exercise server restart, network loss, application restart, capture rotation, and project save/reopen.
- [ ] Verify audit and capture hash chains after the run.
- [ ] Save sanitized logs, matrix CSV, screenshots, project digest, and signed operator result.

## Acceptance rule

A profile is field-ready only when all blocking rows are `PASS`. `BLOCKED` requires a named external
dependency and owner. `FAIL` requires a reproducible fixture or captured stream before a code fix is accepted.
