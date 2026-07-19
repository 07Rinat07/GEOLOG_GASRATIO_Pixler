# Tablet Engine 2.0 — navigation

The tablet uses one camera for every track and for either depth or time axes.

Controls:

- wheel — scroll;
- `Ctrl+wheel` — zoom around the cursor value;
- middle button or `Space + left button` — hand pan;
- `Home`/`End` — start/end;
- `PageUp`/`PageDown` — nearly one viewport;
- `Up`/`Down` — small step;
- scrollbar and go-to stay synchronized with every column.

The camera clamps the window to the real LAS domain and prevents tracks from drifting apart.

## Horizontal viewport and pinned depth

- tracks keep their configured widths and are no longer compressed to fit the window;
- the depth track is pinned on the left;
- all other tracks use a real horizontal scrollbar;
- resizing a track immediately updates the complete horizontal range.

## Mini-map

A full-domain mini-map is shown on the right. Its grey window represents the current viewport. Clicking jumps to a location and dragging pans the shared `TabletCamera` range.

## Peak-preserving LOD

Large LAS curves use a viewport-aware point budget. Each bucket preserves its minimum and maximum, so narrow peaks and valleys remain visible when zoomed out. Original samples return automatically when zooming in.

## Curve geometry cache

The current viewport, point budget, axis and data revision form a render key. Repeated requests reuse peak-preserving geometry from a bounded LRU cache. When a curve render key is unchanged, its graphics item is not updated again.

## Static layers and dirty repaint

Track title, width, grid and axis label use a dedicated static-configuration cache. Every change carries an explicit invalidation reason: data, style, static state, viewport or layout. Changing one track's color, width, grid, label or line style updates only that track; neighbouring track widgets are not rebuilt. Geometry and static caches are invalidated selectively, and the engine records full-versus-partial refresh statistics.

# Tablet Engine 2.0 — Overlay Engine

Dynamic tablet elements are separated into independent cursor, selection, marker, annotation, interval-preview, tooltip and rubber-band layers. Every layer has its own visibility, Z-order and dirty state. Overlay changes do not rebuild curve geometry or static tracks.

## Selection & Interaction Engine

The first slice adds a unified selection manager for tracks and intervals, a shared hit-testing result, and Undo/Redo infrastructure. Selection is updated through the independent Selection overlay without rebuilding curve geometry.

## Selection & Interaction Engine

- hit-testing for track headers and nearest curves;
- track resizing by dragging the boundary handle;
- track reordering by dragging headers;
- Undo/Redo for width and order changes;
- curve selection does not rebuild the geometry cache.

## Selection interaction update

Track and curve selection now supports additive/toggle selection, selected curve details in the inspector, and track context operations with Undo/Redo.

## Practical initial viewport and mouse wheel

Long LAS files no longer open as one vertically compressed picture. Depth data starts in a readable window of up to 200 m (500 ft for feet), while short files remain fully visible. Long time datasets use an approximately 30-minute window. The wheel pans the shared vertical window across every track immediately; `Ctrl+wheel` zooms around the pointer.

Repeated samples mapped to the same depth/time are averaged only for screen geometry. Raw LAS values remain unchanged and misleading horizontal strokes are removed.

## Compact side panels

The LAS curve browser and inspector start collapsed. Narrow icon rails on the left and right open tools on demand and expose shortcuts through tooltips. `Ctrl+Alt+0` collapses all side panels.

## Full-height tracks and column context menu

Tablet tracks now fill the complete available workspace height. The depth column uses a compact ruler without a duplicate rotated label and remains mouse-resizable. Right-click works anywhere inside a column; graphical tracks expose direct actions for adding curves, changing the parameter/curve set, and opening track properties.
