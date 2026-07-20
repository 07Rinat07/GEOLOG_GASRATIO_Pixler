# Editable form captions and stratigraphy

Updated: 20 July 2026

## Editable captions

Every visible tablet column or track has a right-click context menu. **Edit everything in track…**
opens one editor for:

- track title;
- merged section title such as Geology or Gas Data;
- width;
- X-axis caption;
- parameter order within the track;
- user-facing caption of each parameter;
- line colour, width and style;
- linear or logarithmic scale;
- automatic or manual range.

The source LAS mnemonic remains unchanged. Only presentation text is edited, so export and later
parameter resolution remain safe. Replacing curve bindings no longer overwrites a custom track
title.

The same context menu provides **Rename track…** and **Rename section…**. Section renaming is
applied to the contiguous group of columns that share that section title. The main toolbar also
contains an Edit selected track button.

All edits become part of the active layout and are stored with the project, user form, or tablet
preset.

## Stratigraphy catalog

The application includes a factory reference for principal eonothems, erathems, and
systems/periods. Each entry contains a stable internal ID, rank, code/abbreviation, RU/KK/EN
names, standard colour, and parent code.

A factory entry can be overridden inside a project: its code, text, translations, colour, and
description remain editable. It cannot be deleted and can be reset to the factory value. Local
formations, members, horizons, and beds are added as custom records. Project catalog changes are
stored in the project file.

## Filling the Stratigraphy track

1. Enable **Stratigraphy selection** on the toolbar, or hold `Shift`.
2. Drag with the left mouse button from top to bottom in the Stratigraphy track.
3. Select a catalog entry in the dialog.
4. Adjust boundaries, rank, code, name, colour, or description when required.
5. Press `OK`.

Double-click an existing block to edit it again. Right-click exposes interval creation/editing and
track configuration. `Esc` cancels an unfinished drag.

Intervals of the same rank cannot overlap. Different ranks may nest: a period can contain an
epoch, stage, and local formation. Code and name are rendered inside a coloured block on the shared
depth scale.

## Saving

The diskette button and `Ctrl+S` save well intervals, project catalog overrides, section and track
titles, parameter captions, widths, order, scales, ranges, and styles.
