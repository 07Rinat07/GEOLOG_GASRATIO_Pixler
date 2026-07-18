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
