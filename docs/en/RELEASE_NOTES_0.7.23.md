# Release notes 0.7.23

## Main change

The tablet editing path has been rewritten as independent OOP components. Annotations, callouts, track editing and normal navigation no longer compete through multiple unrelated mouse event filters.

## Interaction architecture

- `TabletInteractionRouter` is the single keyboard/pointer dispatch point;
- `AnnotationInteractionHandler` owns annotation creation, selection, move, resize, context actions and editing;
- `TrackEditInteractionHandler` owns track selection and direct opening of the full column editor;
- `TabletEditModeCoordinator` is the single owner of F4/tool state invariants;
- `TabletInteractionWatchdog` safely finishes a gesture if Windows drops a mouse-release event;
- `TabletAnnotationOverlay` is paint/hit-test only and never uses native mouse capture or a widget mask.

## Restored F4 workflow

- an empty plot click selects the track without blocking curve selection;
- a double-click on a curve/gas track opens the full column editor;
- right-click opens the normal track/parameter menu;
- Comment, Callout and Image tools create directly at the clicked track and axis position;
- an existing annotation has priority over the armed creation tool;
- annotations can be selected, moved, resized with eight handles, edited by double-click/F2/Enter and deleted with Delete;
- cancelling a creation tool restores track editing without rebuilding the tablet.

## Regression prevention

The overlay remains permanently transparent to mouse input and cannot retain a stale pointer grab over the tablet. F4 state is centralized: annotation and track handlers are enabled together, and track editing is suspended only while a direct creation tool is armed.

Dedicated unit tests cover the router, mode coordinator, annotation handler, track handler and their combined event pipeline.

## DB → LAS batch converter

This release also includes the completed user-facing batch workflow:

- full target path preview;
- recommended `{source_name}_{mode}.las` mask;
- duplicate-target protection;
- explicit row status/details;
- Open LAS, Open result folder, Retry failed and Close actions;
- safe stop/cancel behavior;
- output is saved automatically to the selected folder, so no second Save action is required.

## Compatibility

The project format, annotation schema and user forms are unchanged. Existing comments, callouts and track settings require no migration.

## Test boundary

PySide6, pyqtgraph and lasio are unavailable in the minimal Linux container. Physical Windows/HiDPI pointer tests and the complete DB → LAS → reopen cycle remain required in the normal application environment.
