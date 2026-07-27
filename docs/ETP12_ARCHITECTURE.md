# ETP 1.2 architecture

## Boundary

The ETP subsystem is split into generated-model transport, a protocol state machine, a read-only
application facade and a Qt worker. No ETP dependency is imported when the package itself is imported;
optional generated runtime modules are loaded only when a real WebSocket session starts.

## Components

- `models.py`: immutable public profiles, negotiated protocols, resources, arrays, channel batches,
  subscriptions and snapshots.
- `etpproto_adapter.py`: WebSocket/TLS/authentication and Avro model encoding/decoding.
- `protocol.py`: message IDs, correlation, multipart FIN, ACK, timeout and unsolicited dispatch.
- `service.py`: negotiation validation, Discovery, Store, Data Array and Channel Subscribe facade,
  reconnect watchdog and subscription restoration.
- `etp12_profiles.py`, `etp12_credentials.py`, `etp12_audit.py`: public settings, secrets and audit.
- `etp12_dialog.py`: persistent QThread/asyncio owner and operator interface.

## State machine

```text
DISCONNECTED → CONNECTING → NEGOTIATING → OPEN
      ↑                                  ↓
      └──── RECONNECTING ← FAILED ← receive-loop error

OPEN → CLOSING → CLOSED
```

The receive loop is the authority for connection failure. It marks the engine FAILED and wakes all
pending requests. The service watchdog then creates a new engine, negotiates a new session and restores
subscriptions. A clean operator close cancels the watchdog before closing the WebSocket.

## Message contract

Client message IDs are even. Requests have correlation ID zero. Responses and multipart parts point
to the original request ID. The engine completes a request only after FIN and returns parts ordered by
message ID. ACK requests are answered independently and never enter the request-response payload list.

## Read-only policy

Public operations are limited to Discovery, Store retrieval, Data Array retrieval, channel metadata and
channel subscription. There is no facade for Put/Delete/Transaction/DataLoad. This is an application
safety boundary rather than only a UI restriction.

## Security

Remote endpoints require WSS and verified certificates. Basic and Bearer secrets are obtained from a
credential store, never from project data. Endpoint profiles and audit records are sanitized. The audit
contains protocol metadata, IDs, timing and outcomes, but no Avro payload.

## Subscription recovery

Each subscription retains its immutable definition, server channel IDs, generation and latest index per
channel. Reconnect marks it RESTORING and resubscribes from the latest retained index. Servers may send
overlap; acquisition deduplication remains downstream and provenance is preserved.

## Remaining interoperability work

A real server matrix must verify endpoint capabilities, auth variants, multipart/chunk behavior,
ChannelData value unions, server-specific URI conventions and reconnect overlap. Streaming batches are
currently displayed and exposed through callbacks; binding them to a new append-only ETP acquisition
session is a subsequent integration slice.
