# Interface workspace 0.7.7

## Main toolbar

The main toolbar now keeps only frequent actions:

- **LAS Editor** for creation, repair, insertion and merging;
- **Form library** as a direct button with no drop-down menu;
- **Constructor** for screen forms, ready headers, assets and print checks;
- project open, data import and project save;
- curve pencil and cursor line.

Specialist commands remain in their thematic menus. Every action has a tooltip and status tip.

## Form editing mode

**F4** toggles a dedicated form-editing toolbar.

When enabled, it provides:

- add graph column;
- edit selected column and parameters;
- move column left or right;
- remove column;
- save the current layout as a user form.

When disabled, structural commands are hidden from the tablet context menu while navigation
and geological data entry remain available.

## Form library

The library is grouped into four sections:

1. factory forms — depth;
2. factory forms — time;
3. user forms — depth;
4. user forms — time.

User JSON files are physically stored under `forms/depth` and `forms/time`. Legacy forms in
the repository root remain readable and move to the appropriate folder on the next save.

A factory form becomes an editable working copy after it is applied to the tablet; the factory
document remains protected. Saving preserves order, widths, captions, text rotation, ranges,
colours, scales and grids.

## Constructor

The Constructor uses side navigation instead of an overloaded tab row:

- tablet forms;
- print forms and headers;
- lithotypes and symbols;
- preflight.

The **Geological-technological investigations — ready blank** preset is visible directly in
the ready-preset gallery. Creating it makes an editable project copy and exposes the header
editor. Primary actions remain visible; columns, mapping, page, symbols and assets are in a
collapsible advanced section.

## Combined LAS export fix

The temporary LAS is now written explicitly as UTF-8. This fixes the Windows failure where
Russian descriptions were written through CP1251 and the lossless composer subsequently read
the temporary file as UTF-8. The final document is converted back to the source encoding.

## 0.7.8 visibility fix

Under the Windows dark theme, the Form Library explicitly uses contrasting dark text on its light panels. Factory depth and time presets remain visible even when no user forms have been saved yet.

## Curve pencil in the tablet — 0.7.9

A persistent **Curve pencil** row is shown above the tablet. Choose a track and source curve, enable the tool, and draw directly in the plot with the left mouse button. The target track scrolls into view automatically. The orange stroke is a preview; releasing the button commits the edit, while `Esc` cancels only the current stroke. Calculated curves are excluded.

## Parameter captions and pencil saving — 0.7.10

Graph headers use a readable name from the LAS description or Sensors.DB. Technical codes such as `S300`, `S720`, `S800`, `S900` and `S50` remain in tooltips/editors instead of replacing the caption. Pencil activation prefers the selected curve and marks the target track with an orange header and `✎`. Dependants recalculate immediately after a stroke, the UI reports “Not saved”, and disk writing occurs only through Save.
