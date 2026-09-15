# WITS0 Windows field reliability gate

## Status

This gate runs on the target Windows workstation connected to real GeoScape/GSWITS traffic.
Release 0.7.96 includes application-level WITS0 transport diagnostics and serialized recovery
manifest updates, but the physical field gate is not considered passed until the checks below are
completed on the real network and sustained traffic.

## Required setup

Record the workstation, Windows build, application build and SHA-256, GSWITS connection mode,
actual IP/port, enabled records and intervals, raw-storage volume, free-space thresholds, retention
policy, NTP source and test operator. Ports shown in vendor screenshots are examples and must not be
assumed.

## Network preflight

Before changing WITS0 framing, parser profiles or channel mapping, verify that the target TCP
listener is reachable from the GEOLOG workstation. From the repository root on Windows PowerShell:

```powershell
.\scripts\wits0_network_preflight.ps1
```

The default target is the current field preset `192.168.0.100:2041`. Another endpoint can be checked
without editing the script:

```powershell
.\scripts\wits0_network_preflight.ps1 -TargetHost 192.168.0.100 -TargetPort 2041
```

The report is written under `build/field-evidence` unless `-OutputPath` is supplied. Keep that report
with the field evidence. `Status=PASS` means the TCP handshake succeeded from the exact workstation
and selected Windows interface. `Status=FAIL` means routing, interface selection, listener state or
firewall must be resolved before parser-level diagnosis. ICMP ping is recorded for context only: a
failed ping does not fail the gate when TCP succeeds.

For the current GeoScape arrangement, verify that the report shows the intended `SourceAddress`,
`InterfaceAlias`, target `RemotePort=2041` and `TcpTestSucceeded=True` before starting WITS0 capture.

## Diagnostic support bundle

The normal application diagnostics ZIP automatically includes recent WITS0 `connections.jsonl`
lifecycle journals from the default application raw directory. The attachment is generated through
an allowlist: connection timestamps, IDs, peer/reason and counters are retained, while unknown
fields are discarded and `raw_file` is reduced to its filename. Each journal attachment is bounded
to the recent 512 KiB and at most eight journals are included.

Raw `.wits` frame files and channel values are never auto-attached to the support ZIP. If full raw
capture is required for the field acceptance evidence, transfer it separately under the site's data
handling rules.

## Minimum run

Run at least 8 hours; 24 hours is preferred. Include normal traffic, one controlled GSWITS restart,
one application restart with an open acquisition session, network interruption and recovery, raw
rotation, project save/reopen, live-monitor pause/resume and history navigation.

## Acceptance evidence

Collect the network preflight report, raw `.wits` segments, chunk indexes, connection journal,
recovery manifest, project file, application log, soak JSON report and screenshots of
connection/live-monitor state. Verify:

- no accepted TCP bytes exist without a raw reference;
- connection IDs and disconnect reasons are complete;
- replay produces the same parsed/discovery result as live capture;
- acquisition sequence and checkpoints continue after restart;
- disk warning/critical thresholds behave as configured;
- active raw files are never removed by retention;
- no unhandled exception, UI freeze or growing memory trend is observed;
- final recovery manifest reports a clean shutdown.

A failed criterion keeps the gate open. The report must identify the failing timestamp, connection
ID, raw segment and corrective build.
