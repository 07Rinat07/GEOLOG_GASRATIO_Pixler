# ETP 1.2 interoperability gate

## Test environment

Record server product/version, endpoint, certificate chain, authentication mode, dataspace, WITSML
object versions, selected channels and test window. Use a read-only service account.

## Security and handshake

- [ ] WSS certificate validation succeeds without disabling verification.
- [ ] WebSocket subprotocol is exactly `etp12.energistics.org`.
- [ ] Password/token is absent from project, profile JSON, audit and screenshots.
- [ ] RequestSession receives one valid OpenSession.
- [ ] Negotiated Core, Discovery, Store, Data Array and Channel Subscribe roles match the server.
- [ ] Unsupported protocol produces a controlled diagnostic.

## Protocol behavior

- [ ] Correlation IDs match every request and response.
- [ ] Multipart response is complete only at FIN and is ordered correctly.
- [ ] ACK-requested server message receives one Acknowledge with correct correlation ID.
- [ ] ProtocolException terminates only the correlated operation.
- [ ] Max message and endpoint capabilities are respected.

## Data access

- [ ] Discovery returns expected Well/Wellbore/Log/Channel resources.
- [ ] Store returns valid WITSML 2.x XML without payload truncation.
- [ ] Data Array metadata and values match an independent reference export.
- [ ] Channel metadata includes correct URI, ID, index kind, UOM and data kind.
- [ ] ChannelData index/value pairs match source instrumentation.

## Recovery

- [ ] Force network loss while subscribed.
- [ ] Session changes to FAILED/RECONNECTING without freezing UI.
- [ ] Bounded reconnect negotiates a new session.
- [ ] All active subscriptions are restored from retained indexes.
- [ ] Overlap is detected/deduplicated downstream; no silent gap remains.
- [ ] Operator close stops reconnect attempts and closes cleanly.

## Soak and evidence

- [ ] Run at least 8 hours; 24 hours is recommended.
- [ ] Record message/ACK/reconnect/subscription counters and memory growth.
- [ ] Verify hash-chained audit after the run.
- [ ] Save anonymized protocol metadata, screenshots and a signed result.
- [ ] Mark the server profile field-ready only after every blocking item passes.
