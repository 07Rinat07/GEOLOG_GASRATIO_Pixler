# Constructor guide

Constructor combines tablet forms, Masterlog print templates, headers, columns, assets, symbols,
and preflight. The interface remains readable in light and dark Windows themes. The recommended
reference Masterlog with editable fields and two replaceable logo slots is shown first.

## Opening and navigation

Choose **Constructor → Open constructor** or press `Ctrl+Shift+K`.

In the tablet-form tab:

- mouse wheel pans the visible depth range;
- `Ctrl + wheel` zooms around the pointer;
- touchpad navigation works over plots, headers, and empty space;
- rapid form switching is protected by debounce and a revision token.

## Tablet forms

The **Tablet forms** tab opens Form Manager. Depth or time forms can be created, copied, edited,
imported, exported, and applied. Review column order, width, curve bindings, scales, grid, units,
and text direction.

After changing a form, save it in the library, apply it to the tablet, and press **Ctrl+S** to save
the current project. Form export creates a separate portable file and does not replace project save.

## Print forms and headers

A Masterlog template provides:

- **Header editor** — a WYSIWYG canvas in millimetres;
- **Form columns** — composition, order, width, curves, and scales;
- **Parameter mapping** — required mnemonics bound to the current dataset;
- **Page and scale** — A0–A4, Letter, Legal, custom, roll, orientation, and depth scale;
- **Depth symbols** — point, interval, curve-parameter, or time anchors;
- **Project images** — graphics import and reuse;
- **Preview** — the same renderer used for final output.

A red dashed boundary shows physical page width. An object to its right will overflow the selected
sheet.

## Header elements

Text, dynamic fields, images, lines, lithology legend, and LBA legend are supported. Coordinates
and dimensions use millimetres. Elements can be moved, duplicated, reordered, rotated, aligned,
and given opacity.

BMP, PNG, JPEG, TIFF, WebP, and SVG support:

- `fit` — preserve aspect ratio inside the box;
- `fill` — fill the box with cropping;
- `stretch` — stretch to the box.

## Text direction and placement

Select a column or track in the structure editor and choose:

- horizontal 0°;
- bottom-to-top 90°;
- top-to-bottom 90°;
- near-top, centered, or near-bottom placement.

The same settings apply to header text, dynamic fields, and lithotype labels. Preview and print use
the stored values.

## Lithotypes and rock patterns

The catalog contains 117 canonical lithotypes. Search works by RU/KK/EN name, legacy name, alias,
and ID. Lithotypes use tiled non-smoothed BMP textures and do not stretch when depth scale changes.

Lithology-legend scopes are:

- rocks used in the well;
- the complete project catalog;
- manually selected rocks;
- used plus selected rocks.

Text over **Lithology** and **Cuttings** patterns is disabled by default. Name, code, and percentage
remain available in the editor and tooltip. Enable code/percentage overlay in track or form-structure
settings for specialized forms.

## Symbols

The catalog contains 19 factory symbols. A print depth symbol selects anchor type, depth/interval,
column, parameter, image, width, height, label, and X/Y millimetre offset. Depth or time remains the
semantic anchor; the offset only refines visual placement.

For interactive insertion directly on a tablet graph, use **F4 → Insert symbol**. The object can be
moved with the left mouse button, resized with eight handles, and saved with the project. See
[ANNOTATIONS.md](ANNOTATIONS.md).

## Preflight before output

The **Preflight** tab checks:

- dataset and required columns;
- header elements outside the page;
- missing images and assets;
- curve bindings and units;
- depth-symbol validity;
- scale, media, and page continuations.

Resolve `error` items before PDF or physical printing. After preflight, open preview and visually
check the header, scales, labels, symbols, and page boundaries.

## Saving and reopen verification

- **Ctrl+S** saves current project changes.
- Saving a form in the library makes it reusable.
- Form/template export creates a separate exchange file.
- PDF and printing do not replace saving the project or form.
- After important changes, close and reopen the project/form, then repeat preflight and preview.

## Ready KazGeology form

**Geological-technological investigations — ready form** targets A3 landscape and includes two
logo areas, well details, legends, construction, colored scales, and manual rock descriptions.
See [KAZGEOLOGY_TEMPLATE.md](KAZGEOLOGY_TEMPLATE.md).
