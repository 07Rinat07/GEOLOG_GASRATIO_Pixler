# WITS Level 0 capture

## Purpose

**File → Capture WITS Level 0...** receives a GSWITS TCP stream and preserves the original bytes
unchanged. This slice is a safe raw-capture boundary: it does not yet commit values to a Dataset or
execute alarms.

## TCP server setup

Use this mode when GSWITS is configured as an **Outgoing connection (TCP client)**.

1. Select **Incoming connection - TCP server**.
2. Use `0.0.0.0` to listen on all local interfaces, or enter one interface address.
3. Enter the same port used by GSWITS.
4. Select the raw-data directory and press **Start capture**.
5. Save the GSWITS network settings and verify its connected indicator.

## TCP client setup

Use this mode when GSWITS is configured as an **Incoming connection (TCP server)**.

1. Select **Outgoing connection - TCP client**.
2. Enter the GSWITS computer address and port.
3. Press **Start capture**.
4. Pixler retries automatically after a disconnect with a bounded increasing delay.

## Stored data

Each connection receives a separate directory. Binary `*.wits` files contain the exact incoming
bytes; `*.chunks.jsonl` files record the UTC arrival time, offset, and size of each TCP chunk.
Segments are never overwritten and can be used for deterministic replay.

## Verification

**Latest frames** shows frames delimited by `&&` and `!!`. **Connections and errors** shows
connections, disconnects, raw-segment creation, and failures. Closing the window stops the worker
and closes its files.

## Limitations

- the built-in GeoScape profile is based on the GSWITS manual and must be confirmed with real raw data;
- unknown fields are not interpreted in this slice;
- do not expose a WITS0 port directly to the Internet;
- raw files do not replace project saving with **Ctrl+S** and remain independent files after reopen.
