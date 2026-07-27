# GEOLOG GASRATIO@Pixler 0.7.81 — WITSML 2.x / ETP 1.2 client foundation

## Secure WebSocket session

Added a headless ETP v1.2 client over binary WebSocket frames. The production adapter requests the
`etp12.energistics.org` subprotocol, requires `wss://` for remote hosts, validates TLS by default,
limits message size, configures ping/open/close timeouts and rejects credentials embedded in URLs.
Unencrypted `ws://` is available only for explicitly enabled localhost testing.

## Session and protocol negotiation

`RequestSession` advertises ETP 1.2 Core, Channel Streaming, Discovery, Store, Data Array and Channel
Subscribe roles plus WITSML 2.0/2.1 and EML object families. `OpenSession` is validated before the
facade becomes usable. Unsupported protocols fail at the service boundary instead of producing an
ambiguous server error.

## Correlation, multipart and acknowledgement

Client message identifiers are even and monotonically allocated. Pending requests are indexed by
message ID, response parts are correlated and accumulated until FIN, and multipart results are
returned in message-ID order. A server message carrying the ACK flag receives an automatic Core
Acknowledge whose correlation ID points to the server message ID. ProtocolException terminates the
matching pending request with a typed error.

## Discovery, Store and Data Array

The read-only facade supports Discovery `GetResources`, Store `GetDataObjects`, Data Array metadata
and Data Array values. Returned resources, objects, array identifiers, dimensions and values are
converted to immutable project-side models. No ETP write, delete or transaction method is exposed.

## Channel Streaming and Channel Subscribe

The client reads unsolicited ChannelData from both simple Channel Streaming and Channel Subscribe.
For recoverable store subscriptions it requests channel metadata, maps channel URIs to numeric IDs,
subscribes from an explicit or latest index, emits immutable channel batches and retains the last
observed index for every channel.

## Reconnect and subscription recovery

A watchdog detects a failed receive loop, performs bounded exponential reconnect attempts, repeats
session negotiation and restores non-closed subscriptions. Recovery starts from the greatest retained
channel index; downstream acquisition remains responsible for overlap deduplication. Subscription
state and generation are visible in immutable session snapshots.

## Credentials and audit

Public profile JSON contains no password or bearer token. Windows uses a dedicated Credential Manager
namespace `GEOLOG_GASRATIO_Pixler/ETP12/`; non-Windows development keeps secrets only in memory. The
append-only JSONL audit is SHA-256 chained, sanitizes endpoints and excludes message payloads and
Authorization data.

## Desktop integration

Added **File → WITSML 2.x / ETP 1.2…**. A persistent QThread owns the asyncio loop and WebSocket
session, keeping network and Avro work outside the GUI thread. The dialog provides connection profile,
Discovery tree, Store object preview, Data Array access, channel metadata, subscribe/unsubscribe,
current values and protocol metrics.

## Validation and limitations

The headless ETP/state-machine gate covers correlation, multipart FIN, ACK, audit, secure profiles,
Discovery, Store, Data Array, explicit reconnect, automatic reconnect and subscription restoration.
The generated `etptypes`/`etpproto` runtime could not be installed from the build container's package
index, so real Avro wire interoperability remains an external gate. PySide6/pyqtgraph are also absent,
therefore the complete Qt runtime suite was not executed. A real ETP 1.2 server test is mandatory
before field use.

Project format remains v20, form schema v8 and tablet layout v18. The compact-column and form-library
contracts remain ready: 50%, 48, 80, user forms, duplicate-name and whitespace protection are unchanged.
