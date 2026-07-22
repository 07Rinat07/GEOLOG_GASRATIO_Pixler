# Hotfix report 0.7.20

## Scope

The release fixes two user-visible defects:

1. Time channels such as `TIME: 7648.2 S` were presented as raw numbers in some views and could differ across Windows/Linux conversion paths.
2. Curve-bound annotations could paint over track headers, and compact F4 actions still required a modal creation workflow rather than direct placement.

## Date/time architecture

A new `services/time_display.py` service is the single presentation boundary for:

- NumPy `datetime64`;
- Unix seconds and milliseconds;
- Delphi/OLE Automation serial dates;
- elapsed seconds/minutes/hours;
- elapsed time combined with a dataset registration start;
- time indexes and time curves.

The service uses explicit epochs and `timedelta`; application source no longer calls `datetime.fromtimestamp` or `utcfromtimestamp`. The normalized user format is `DD.MM.YYYY HH:MM:SS`, with fractional seconds only when present. Without an absolute origin, elapsed values render as `HH:MM:SS` rather than an unexplained scalar.

Integrated presentation paths:

- tablet cursor summary and per-track cards;
- LAS table index and time-curve cells;
- standalone curve cursor;
- Paradox first/last-row preview;
- annotation axis/value editor;
- curve-value popup and persisted printable label;
- project data inspector;
- Masterlog point inspection and pinned inspection text.

## Annotation architecture

`TabletAnnotationOverlay` remains one tablet-wide layer so boxes can cross track boundaries, but it now receives a graph-body rectangle calculated from the rendered pyqtgraph ViewBoxes. Painting, hit testing, mouse masking, movement constraints and print painting all intersect this rectangle. Therefore headers and parameter captions are not part of the annotation canvas.

F4 actions are checkable tools. A left click in a plot computes the exact track, active depth/time coordinate and horizontal fraction. Callouts/comments are inserted immediately into the existing well annotation model, selected, and become movable/resizable without opening a dialog first. Images retain a file-selection dialog after the placement click. Full text/style editing remains available through double-click, F2, Enter, toolbar actions and context menus.

Fresh objects near a vertical edge choose an initial offset inside the current plot viewport.

## Compatibility and persistence

No project schema migration was introduced. Existing `annotation` and legacy `depth_annotation` records remain valid. Geometry is still committed through the controller/history path; source LAS/DB files remain read-only.

## Validation

- `python -m compileall -q src tests`: passed.
- Focused dependency-free regression suite: 147 passed.
- RU/KK/EN resources: 1500 identical keys; placeholder sets synchronized.
- JSON validation: passed.
- No `fromtimestamp`/`utcfromtimestamp` calls remain in application source.

PySide6, pyqtgraph and lasio are unavailable in this container, so physical Windows mouse interaction, PDF/print comparison and DB→LAS round-trip must still be smoke-tested in the normal packaged environment.
