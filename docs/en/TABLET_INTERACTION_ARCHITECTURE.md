# Tablet interaction OOP architecture

## Purpose

The architecture separates rendering from input handling and prevents a transparent widget from blocking the entire tablet editor.

## Components

### `TabletInteractionRouter`

Receives normalized `TabletInputEvent` objects and dispatches them by priority. It is the only owner of logical gesture capture; native `grabMouse()` is never used.

Handler order:

1. existing annotation;
2. armed annotation creation tool;
3. track selection/editing;
4. normal curve, geological interval and navigation logic.

### `TabletEditModeCoordinator`

Owns all F4 invariants: annotation and track handlers are enabled together, track interaction is suspended only while a creation tool is armed, and disabling F4 always disarms the tool and restores cursor state.

### `AnnotationInteractionHandler`

Owns selection, creation, drag/resize, double-click, F2/Enter/Delete and context actions. It does not paint. A geometry change is committed to the model once, after pointer release.

### `TrackEditInteractionHandler`

A single click selects the track but passes through for curve selection. A double-click opens the full editor for supported track types.

### `TabletAnnotationOverlay`

Paint/hit-test only. It is permanently `WA_TransparentForMouseEvents`, has no mouse handlers, widget mask or pointer grab. Drag/resize repaints only the annotation dirty region.

### `TabletInteractionWatchdog`

Checks the real left-button state while a logical gesture is active. If Windows drops the release after Alt+Tab, a modal dialog or monitor transition, the watchdog safely completes the gesture and clears router capture.

## Extension rules

A new tablet tool implements the router handler interface. It must not install a competing canvas-wide event filter, use native pointer capture or directly change another tool's state. Mode transitions go through the coordinator.

## Invariant tests

Tests verify paint-only overlay behavior, no native capture/mask, one commit per drag, track pass-through, annotation priority, restored track editing after tool cancellation, and capture cleanup after window deactivation or lost release.
