# Hotfix report 0.7.23 — OOP tablet interaction routing

## 1. Problem

Several independent mouse paths existed simultaneously: the tablet viewport event filter, per-track event filters, `QGraphicsObject` handlers and a transparent canvas-wide annotation widget. After a lost release or an incomplete mode reset, one path could retain ownership and block both annotation editing and track/curve editing.

Observed regressions included:

- F4 annotation buttons or direct creation no longer reacting;
- existing callouts/comments becoming impossible to select, move, resize or edit;
- left/right click on a track no longer opening selection or parameter actions;
- the full curve/parameter column editor becoming inaccessible;
- the transparent overlay remaining effectively active after a drag;
- future hotfixes fixing one interaction while breaking another.

## 2. Architecture implemented

### `TabletInteractionRouter`

A platform-neutral priority router now receives normalized pointer/key events. It is the only owner of logical gesture capture. It dispatches to handlers in registration order and explicitly clears capture on release/cancel/deactivation.

### `TabletEditModeCoordinator`

A dedicated coordinator owns all F4 invariants:

- annotation and track handlers are enabled together;
- track editing is suspended only while a direct creation tool is armed;
- disabling F4 disarms the active tool;
- partial or contradictory mode states cannot be produced by individual widgets.

### `AnnotationInteractionHandler`

Owns annotation selection, direct creation, drag, eight-handle resize, double-click/F2/Enter editing, Delete and context actions. Existing annotations have priority over the active creation tool. One gesture commits one geometry change after release.

### `TrackEditInteractionHandler`

A single click selects the track but passes through to normal curve selection. A double-click opens the full editor for regular curve/gas/DEXP tracks. Geological interval tracks retain their specialized double-click behavior.

### `TabletInteractionWatchdog`

During an active gesture it checks the actual left-button state. If Windows loses a release event after Alt+Tab, a modal dialog or monitor transition, the watchdog finalizes the gesture. Window deactivation, hide and `UngrabMouse` also clear router state.

### Paint-only `TabletAnnotationOverlay`

The overlay is permanently `WA_TransparentForMouseEvents`. It performs painting and hit-testing only. It does not install a widget mask, call `grabMouse()`/`releaseMouse()`, or implement mouse event handlers.

The internal `TabletAnnotationItem` has also been stripped of its old mouse/hover/context handlers so no second annotation interaction path remains.

## 3. Event priority

1. Existing annotation under the pointer.
2. Armed Comment/Callout/Image creation tool.
3. Track selection and full track editor.
4. Existing curve selection, geological interval editing, context menus and navigation.

This priority preserves annotation editing without taking ordinary track actions away from the user.

## 4. User workflow after the fix

### Track and parameter editing

1. Press F4.
2. Leave annotation creation tools unarmed.
3. Click a track to select it.
4. Double-click a normal curve/gas track to open its full editor.
5. Right-click the plot or parameter header for add/remove/change/settings actions.

### Annotation creation/editing

1. Press F4.
2. Select Comment, Callout or Image.
3. Left-click the exact track/depth/time point.
4. Move the box by its body and resize through eight handles.
5. Double-click, F2 or Enter to edit; Delete to remove; right-click for object actions.
6. Press Escape to disarm the creation tool and immediately return to track editing.

## 5. Batch DB → LAS workflow included

The release includes the completed batch-converter UX from the development branch:

- full output path preview before conversion;
- safe `{source_name}_{mode}.las` default mask;
- duplicate target detection;
- explicit status/details per operation;
- Open selected LAS, Open result folder, Retry failed and Close actions;
- safe stop/cancel behavior;
- direct saving to the selected folder, with no hidden second Save step.

## 6. New files

- `src/geoworkbench/tablet/interaction_router.py`
- `src/geoworkbench/tablet/annotation_tool.py`
- `src/geoworkbench/tablet/track_edit_tool.py`
- `src/geoworkbench/tablet/edit_mode_coordinator.py`
- `src/geoworkbench/tablet/interaction_watchdog.py`
- `tests/test_tablet_interaction_router.py`
- `tests/test_annotation_tool_router.py`
- `tests/test_track_edit_tool.py`
- `tests/test_tablet_edit_mode_coordinator.py`
- `tests/test_tablet_edit_pipeline.py`
- RU/KK/EN release notes and interaction architecture documents.

## 7. Main modified files

- `src/geoworkbench/tablet/tablet_view.py`
- `src/geoworkbench/tablet/annotation_graphics.py`
- interaction/source-contract tests;
- root and RU/KK/EN README, annotation guide, project status and plan;
- `docs/CHANGELOG.md`, `docs/TESTING.md`, version metadata.

## 8. Compatibility

- project schema unchanged;
- annotation schema unchanged;
- old `depth_annotation` compatibility retained;
- existing comments/callouts/images remain readable;
- user tablet forms and track definitions require no migration;
- Paradox sources remain read-only.

## 9. Validation

- Python compilation: passed;
- dependency-free regression suite: 603 passed, 1 skipped;
- focused OOP interaction suite: passed;
- 20 JSON resources parsed successfully;
- RU/KK/EN catalogs contain 1549 identical keys with matching placeholders;
- no native `grabMouse`, `releaseMouse` or `setMask` call remains in the tablet interaction implementation.

## 10. Environment boundary

The container does not contain PySide6, pyqtgraph or lasio. Therefore the following must still be confirmed in the normal Windows environment:

- physical mouse drag/resize and lost-release recovery;
- Windows/HiDPI cursor and double-click behavior;
- PDF/physical print visual comparison;
- complete DB → LAS → reopen round-trip.
