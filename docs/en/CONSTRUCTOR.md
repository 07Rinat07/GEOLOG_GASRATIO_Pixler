## Contrast and reference Masterlog — 0.7.11

Constructor navigation, lists, tables, tabs and collapsible sections now use explicit colours and remain readable under dark Windows themes. The recommended reference Masterlog with editable fields and two replaceable logo slots is shown first.

# Constructor guide

Open **Constructor → Open constructor** or press `Ctrl+Shift+K`.

The tablet-form tab opens the existing Form Manager. Rapid selection is debounced and guarded
by a revision token. Wheel pans depth, `Ctrl + wheel` zooms around the pointer, and touchpad
navigation also works over plots, headers and empty tablet areas.

The print tab provides the WYSIWYG header editor, columns, curve mapping, page and scale,
depth symbols, project images and final preview. The canvas uses millimetres. A red dashed
line shows the physical page width; content to its right will overflow.

Supported page profiles: A0–A4, Letter, Legal, custom and roll, with portrait or landscape
orientation where applicable. Header elements include text, dynamic fields, images, lines,
lithology legend and LBA legend. Images may be BMP, PNG, JPEG, TIFF, WebP or SVG and support
fit, fill, stretch, rotation and opacity.

The asset tab contains 117 lithotypes and 19 depth symbols with multilingual names, aliases,
thumbnails and checksums. Lithotypes use tiled non-smoothed patterns. Legend scopes are used,
all, manually selected, and used plus selected.

Depth symbols support point, interval, curve-parameter and time anchors. Choose the column,
parameter, image, size, label and X/Y millimetre offsets. The semantic depth anchor remains the
source of truth while offsets provide precise visual adjustment.

Run preflight before output. It checks datasets, columns, header overflow, missing resources,
curve bindings and depth-symbol validity.

## Text direction and placement

Select a column or track in the form structure editor and choose horizontal 0°, vertical
bottom-to-top 90°, or vertical top-to-bottom 90°, together with near-top, centred, or near-bottom
placement. Header text, dynamic fields, and individual lithotype labels expose the same settings.
Centre is the default, and preview/printing consume the persisted values directly.

## Standard lithotypes in working editors

All 117 supplied patterns are immediately available in the lithology interval selector and in all
four cuttings-composition rows, with a real tiled thumbnail. The catalog can add project rocks,
override a factory entry, or reset that override.

A header may contain either a dynamic lithology legend or one **`lithotype_swatch`** element.
The swatch supports pattern-only, pattern-and-name, or pattern-code-name modes, plus label
rotation and vertical placement.

## Exact rock patterns and labels

The standard rocks use the original BMP patterns from both supplied catalogs. Each bitmap is
tiled without smoothing and remains at its native pixel scale while the depth view is zoomed.

Text over the **Lithology** and **Cuttings** patterns is disabled by default. Names, codes and
percentages remain available in the editor and tooltip. A specialised form can enable **Show
code/percentage over pattern** in the track editor or form-structure editor.

## KazGeology ready blank 0.7.5

Masterlog presets now include **“Geological-technological survey — ready blank”**. It targets A3 landscape and includes two logo upload slots, well metadata, legends, construction, coloured scales and manual rock descriptions. Guide: [KAZGEOLOGY_TEMPLATE.md](KAZGEOLOGY_TEMPLATE.md).
