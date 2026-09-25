# WITS0 live monitor

## Purpose

The **Monitor** tab renders a read-only projection of the growing WITS0 Dataset. It does not mutate
`AcquisitionSession`, stop TCP intake, or bypass `AcquisitionController`.

## Current values

The user selects channels on the left. Each row shows the latest finite value, unit, and quality.
If the newest row has no channel value, the previous finite value remains visible with a `missing`
state. The `stale` state is calculated from the UTC reception timestamp.

## Operator stream state

The monitor header separates presentation mode (LIVE/LIVE PREVIEW/view paused) from the health of
the current read-only projection: **WAITING FOR DATA**, **DATA FLOWING**, **DATA STALE**, or
**ERRORS/GAPS PRESENT**. Health is derived from the current snapshot values and quality flags; it
does not infer that TCP intake or acquisition has stopped. Tooltips direct no-data cases to TCP,
byte/frame counters and Import Review mapping, stale cases to the source/network, and
invalid/source-gap cases to events and diagnostics. A live-projection refresh error is likewise
reported as a display failure rather than an acquisition stop.

## Time and depth axes

**Automatic** uses the active Dataset index. **Time** and **Depth** use a real index when available.
When a secondary axis is absent, the live monitor creates a read-only axis only:

- UTC time from `AcquisitionRecord.received_at`;
- depth from a reviewed semantic depth curve.

A derived axis is not added to the Dataset and is not persisted in the project.

## Auto-follow, pause-view, and history

Auto-follow displays a configured trailing window ending at the newest point. Disabling it enables
history pan and zoom. **Pause view** freezes the visible row count while acquisition continues to
accept and append data. Resume catches up to the current tail.

## Downsampling

`select_visible_samples()` limits points in the selected window while retaining peaks and NaN
breaks. The source Dataset and append-only records remain unchanged. The footer reports source and
rendered point counts.

## Quality and gap markers

The plot displays source-sequence gaps, large axis intervals, invalid values, and missing spans.
Marker provenance comes from append-only records. Markers are diagnostic support and do not replace
mud-logging specialist decisions.

## Operator forms and full-screen mode

A form can be selected **before connection**. Factory forms remain defaults, while every working
form is editable: channels and plots can be added or removed, the axis/history window/point limit
can be changed, and the result can be saved. **Save form** persists overrides by canonical
mnemonic instead of session-specific curve IDs; **Reset** restores the factory template.

The monitor is adaptive. The parameter sidebar can collapse and the live view can detach into
full-screen mode and return without stopping intake or rebuilding the acquisition runtime. The
selected form must survive the LIVE PREVIEW → persistent-runtime handoff.

## Live derived curves and engineering events

WITS-CALC-01 adds WH/BH/CH, Pixler C1/C2–C1/C5 and DEXP/DEXPC as virtual read-only channels.
The same versioned formula registry used by batch calculations is reused; Qt/UI does not contain
a second formula implementation. DEXP is available only with valid ROP/RPM/WOB/BIT and verified
unit conversion; DEXPC also requires actual and normal mud density.

The UI keeps three concepts separate:

- **fluid screening** from Haworth/Pixler;
- **gas origin/context**: background, formation show, connection gas, trip gas, circulated gas,
  or elevated-unclassified;
- **threshold alarm** for a configured channel limit.

A colored line or band remains anchored to the true event depth/time. Its text is rendered as a
compact horizontal badge near the plot edge. Nearby badges are staggered visually without moving
the actual event coordinate.

## Min/max alarms

WITS-ALARM-01 defines optional per-channel min/max, visual/audio enable flags, hysteresis,
debounce/minimum-duration, acknowledgement and global mute. An alarm is parameter supervision,
not a geological conclusion. Sound is emitted on state transition rather than on every sample.

## Limitations and acceptance

The operator dashboard groups compatible channels into engineering panels and automatically splits
incompatible units into adjacent tracks with independent X autoscaling. Workspace channel selection
is persisted by canonical mnemonic rather than session-local `curve_id`, so reconnect or a new
Dataset does not depend on stale internal IDs. Schema-v1 `selected_curve_ids` are accepted only as
a migration fallback and are rewritten as schema-v2 on the next save. Axis, auto-follow,
pause-view, and history-window settings persist as before.

The transient LIVE PREVIEW keeps at most the latest 2000 frames. Its derived Dataset, curve arrays,
preview-session records, and record-id index are bounded as well: when the upper threshold is
reached, the preview runtime is rebuilt from the retained frame window while keeping stable curve
IDs. Persistent reviewed acquisition is not pruned by this mechanism.

If any older preview frame has already been evicted, persistent backfill now fails closed: session
start reports the evicted/retained counts and the retained time range, and no AcquisitionSession is
created. The in-memory tail therefore cannot be silently presented as complete history. Replay of
the available raw interval and explicit selection of a later boundary remain the next WITS-MEM-01
slice. A Windows Qt smoke test and validation with real anonymized GSWITS raw traffic remain
mandatory.
