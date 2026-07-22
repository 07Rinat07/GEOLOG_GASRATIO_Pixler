# Professional annotation layer — 0.7.17

## Interaction hotfix 0.7.17

- the compact F4 **Callout**, **Comment** and **Image** actions now open the focused editor instead of failing inside the dialog constructor;
- the focused editor has explicit **Save** and **Cancel** actions, while its Geometry tab controls initial offsets, width and height;
- in F4 mode, pointer events over an annotation are delivered to the annotation rather than the curve or track below it;
- drag the box by its background/border, resize with the lower-right handle, double-click to edit and right-click for the object menu;
- a new callout starts with a clearly visible leader and places its text box on the available side of the track.

The annotation layer adds persistent explanations to depth/time tablets, graphs and print forms. Every object is stored with the current well in the project instead of being a temporary UI label.

## Quick access

1. Open a tablet and press **F4**.
2. Use the compact **Callout**, **Comment**, **Image** buttons or open **Annotations and callouts…**.
3. Right-click the exact graph location to create an object at that coordinate.
4. Double-click an existing annotation to open the unified appearance editor.
5. In F4 mode, drag the body to move it and use the lower-right handle to resize it.

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
