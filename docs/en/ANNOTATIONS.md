# Professional annotation layer — 0.7.61

## Insert a symbol from the catalog — 0.7.61

1. Open the tablet and enable form edit mode with **F4**.
2. Select **Insert symbol** on the compact toolbar or use the same command in the graph context menu.
3. Find a symbol by name, category, or alias and select its catalog row.
4. Keep **Crop background around symbol** enabled for the transparent cutout, or clear it to use the original background-preserving image.
5. Select the track, optional curve parameter, exact depth, and initial width/height.
6. Press **Insert**. The symbol appears on the graph and is selected automatically.
7. Drag it precisely with the left mouse button. Resize it with the eight corner and side handles.

With a parameter selected, the object is curve-anchored at the specified depth; without a parameter,
it remains depth-anchored inside the selected track. The image is copied into project-owned storage,
so the external BMP/PNG file is not required after saving. The symbol ID and background mode persist
with the annotation. Screen, PDF, and printer output use the same object.

### Saving, reopening, and export

A symbol is not written to disk by a separate command. Inserting, moving, or resizing it marks
the current project as modified. Press **Ctrl+S** or choose **File → Save**. The save operation
records the project-owned image, catalog identifier, background mode, track, parameter or
depth-only anchor, depth, position, size, appearance, visibility, lock state, and print flag.

Control check:

1. save the project with **Ctrl+S**;
2. close it through the normal close command;
3. reopen the same project;
4. verify position, size, depth, track, parameter, and background mode;
5. open preview or PDF when the symbol must be printed.

If the project is closed and saving is declined, the insertion and every edit made after the last
save are lost. PDF, a screenshot, and physical printing do not replace project saving. The
external BMP/PNG is not required after a successful save because the project owns an internal copy.

### Precise editing and safe reversal

- a single click selects the symbol and displays eight resize handles;
- dragging the object body with the left mouse button changes its position;
- dragging a handle changes width and/or height;
- **Undo** reverses the last completed gesture and **Redo** reapplies it in the current session;
- a locked object must first be unlocked in the annotation editor;
- **Delete** or the delete command removes the selected object after confirmation;
- the print flag controls whether the symbol appears in preview, PDF, and physical printing.

## Deletion and current-form scope — 0.7.27

An annotation can be removed through four equivalent paths: the object context menu, the **Delete** key, the full manager button, and the **Delete annotation** button in the focused editor. After confirmation the object is removed from the model, disappears immediately and remains recoverable through Undo.

Every object has a stable scope for the current dataset and tablet form. Switching forms hides comments and callouts from the original form; returning restores them. Editing tracks inside the form does not change the scope. Saving the tablet as a user form rebinds linked objects to the new form. Legacy projects without a scope migrate automatically on first open.

## OOP interaction routing 0.7.23

One `TabletInteractionRouter` dispatches input to an existing annotation, an armed creation tool, track editing and then normal curve logic. `TabletAnnotationOverlay` is paint-only: it is permanently mouse-transparent and never installs a widget mask or native pointer grab. `TabletEditModeCoordinator` owns F4 state, so cancelling a creation tool always restores column selection and full track editing.

Dragging and resizing repaint only the union of the old and new object footprints. Tracks, curves, headers and the project tree are not rebuilt. One gesture creates one Undo command; a click without movement does not modify the project.

## Graph-body clipping

Frames, text, leaders and resize handles are painted only inside the graph body. A curve-bound object cannot cross over track headers or parameter captions. Near a top/bottom edge the initial offset is automatically placed inside the visible plot.

## Free editing across the complete tablet

An annotation is no longer hosted by one graph track. Coordinates are shared across the tablet, so the box can be dragged across column boundaries. There is no full-size translucent QWidget above the plots: a hidden manager stores geometry and each visible object is painted as a small independent sprite limited to its own bounds. Its depth/time/curve anchor remains attached to data while box position and size are persisted in the project.

A single click exposes eight handles at the corners and side midpoints. Drag the fill to move; drag any handle to resize. Double-click, F2, Enter or the Edit selected toolbar button opens the editor. Delete or the Delete selected button removes the object after confirmation. Right-click opens its context menu.

Annotations are omitted from the project/settings tree and managed through the separate “All…” dialog, preventing navigation clutter.

## Scroll synchronization 0.7.19

The annotation screen position is remapped whenever the visible depth or time range changes. Mouse wheel, scrollbar, panning, go-to and zoom move the anchor with the data while keeping the saved box offset, width, height and style unchanged. When the anchored depth leaves the visible interval, the comment leaves the viewport as well.

## Interaction hotfix 0.7.17

- the compact F4 **Callout**, **Comment** and **Image** actions now open the focused editor instead of failing inside the dialog constructor;
- the focused editor has explicit **Save** and **Cancel** actions, while its Geometry tab controls initial offsets, width and height;
- in F4 mode, pointer events over an annotation are delivered to the annotation rather than the curve or track below it;
- drag the box by its background/border, resize with the corner and side handles, double-click to edit and right-click for the object menu;
- a new callout starts with a clearly visible leader and places its text box on the available side of the track.

The annotation layer adds persistent explanations to depth/time tablets, graphs and print forms. Every object is stored with the current well in the project instead of being a temporary UI label.

## Quick access

1. Open a tablet and press **F4**.
2. Use the compact **Callout**, **Comment**, **Image** buttons or open **Annotations and callouts…**.
3. Select a tool and left-click the exact track and depth/time position; right-click remains an alternative context workflow.
4. Double-click an existing annotation to open the unified appearance editor.
5. In F4 mode, drag the body to move it and use the eight corner and side handles to resize it.

## Object types

- **Callout** — text box with a leader and arrowhead.
- **Comment** — standalone text box.
- **Curve value** — a saved exact parameter value at a selected depth.
- **Image** — project-owned PNG/JPEG/BMP/TIFF/WebP/SVG content.
- **Symbol** — a graphic mark with an optional caption.

## Anchors

An object can be bound to a track, depth, time or a specific curve. Curve annotations retain the mnemonic, parameter value, unit, depth and active axis. Zooming keeps the anchor on the data while the body remains readable.

Annotations belong to the well rather than to one source LAS curve. Creating or merging a LAS dataset therefore does not remove them, and merge Undo/Redo leaves the annotation layer intact.

## Appearance

The unified editor controls font family/size/emphasis, text/fill/border/leader colors, opacity, line styles and widths, horizontal and vertical alignment, arrowhead, corner radius, padding, shadow blur and offsets, rotation, body geometry, visibility, locking and print permission. Professional, information, warning, critical and neutral presets are included.

## Curve values

Clicking a curve shows its mnemonic, exact value, unit and depth. **Save value for print** creates a normal editable value callout; **Cancel** closes the popup without modifying the project. The same command is available from the graph context menu.

## PDF and printing

Tablet preview, PDF and physical printing render the same graphics item. The direct Masterlog renderer reads the same persisted model and respects track/depth/curve anchors, images, background, border, leader, shadow and typography. Clear **Print** to keep a service note screen-only.

## Compatibility

Legacy `depth_annotation` objects are opened as depth callouts with no manual migration. New objects use the versioned `annotation` schema. Images are copied into project resource storage, so external file paths are not required.
