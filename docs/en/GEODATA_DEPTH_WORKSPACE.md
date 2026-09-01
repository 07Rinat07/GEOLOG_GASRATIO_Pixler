# GeoData depth workspace

Updated: 20 July 2026

The **Integrated mud logging form — geology, drilling and gas** is the interactive screen for daily review and manual entry of
geological and drilling data on one depth coordinate. It is separate from the printable Masterlog:
the workspace is used for editing, while the Masterlog is the final composite report with an
independently editable header.

## Workspace structure

The form is grouped into three sections.

### Geology

1. Depth.
2. Stratigraphy / age.
3. Lithology.
4. Cuttings log.
5. Rock and cuttings description.
6. Calcimetry.
7. LBA.

### Technology

First graphical column:

- weight on bit `WOB`;
- standpipe/manifold pressure `SPP`;
- torque `TQ`;
- rate of penetration `ROP`.

Second graphical column:

- inlet mud density `MW_IN`;
- hook load `HKLD`;
- rotary speed `RPM`;
- inlet flow `FLOW_IN`.

### Gas data

- working-screen absolute composition: calculated total gas `TG_CALC`, `C1`, and `C2`; additional components can be added to a user copy;
- relative composition: `C1_REL`, `C2_REL`, `C3_REL`, `C4_REL`, and `C5_REL` as percentages of the available hydrocarbon-component sum.

Relative composition is not the same as Gas Ratio/Pixler ratios. `C1/C2`, `C1/C3`, `C2/C3`,
and `C1/(C2+C3)` are calculated separately and belong in a dedicated gas-analysis form. When
all components are missing for a sample, `TG_CALC` remains `NULL/NaN` instead of becoming a
false zero.

Column order is retained by the form. The depth track is not forcibly moved to the left or pinned
outside the layout. All tracks use one parameter-header height and one vertical coordinate, so the
same depth is aligned horizontally across every section.

## Form library

The factory-form manager exposes only the curated working set:

- Integrated mud logging form — geology, drilling and gas;
- MASTERLOG — geological and geochemical form;
- Engineering and drilling monitoring — time form.

Legacy system IDs remain loadable for existing projects, but experimental and duplicate factory
forms no longer clutter the manager. Factory forms are read-only; create a user copy before
changing columns, order, widths, bindings, or styles.

## Creating and editing lithology

1. Hold `Shift` in the Lithology track.
2. Press the left mouse button and drag from top to bottom.
3. Release the button.
4. Correct the numeric boundaries and select exactly one rock type.
5. Press `OK`.

Double-click an existing interval to edit its top, bottom, and rock type or to delete it. The same
object is updated; no duplicate interval is created.

## Creating and editing a cuttings sample

`Shift + left drag` is available in Cuttings, Calcimetry, and LBA tracks. Releasing the mouse opens
one shared sample editor based on the supplied GeoData working dialogs, containing:

- editable top and bottom;
- up to four rock components;
- a percentage for each rock, with an exact total of `100%`;
- no LBA result or one of `LB`, `MB`, `MSB`, `SB`, `SAB`;
- LBA intensity from 1 to 5;
- optional calcite and dolomite, with a combined maximum of `100%`;
- rich rock/cuttings description;
- interpretation or conclusion.

Double-clicking the sample in any linked track reopens the same editor. The existing `sample_id` is
updated atomically, so Cuttings, LBA, Calcimetry, and Description are refreshed together. The
sample can also be deleted from that dialog.

## Description editor

A saved sample description is rendered both in the dedicated description track and in the
on-screen and printed column whose system type is Interpretation. Its displayed heading may be
renamed from the context menu or form editor, for example to Cuttings log; the system type and
project compatibility do not change.

In Select mode (`Alt+1`), hold `Shift` and left-drag in an Interpretation or Rock description
track. A dedicated editor opens without requiring rock percentages. Correct the exact top and
bottom, select a RU/KZ/EN language and ready template, or enter arbitrary text. Double-click a
saved description to reopen it. Deleting the description preserves composition, LBA, and
calcimetry.

The **Text alignment** list applies left, centre, or right alignment to the complete description.
**Wrap words** is enabled by default and is stored for each description. Wrapping may be disabled;
the font still shrinks to the available width and height. Every track-width change recalculates the
fit against the actual visible viewport. If
the complete text cannot fit at the safe minimum, the tablet shows an ellipsis; zooming in restores
the complete text. Painting is strictly clipped to the interval top and bottom, and shortening does
not modify the stored rich text.

Descriptions can be typed directly or pasted from Excel/the clipboard. The editor supports:

- font family and size;
- bold, italic, and underline;
- superscript and subscript;
- text colour and highlight/background colour;
- left, centre, and right alignment;
- optional automatic word wrapping;
- engineering and geological symbols;
- embedded images and cuttings photographs;
- persistence of rich formatting in the project.

Text is rendered within the sample interval, wrapped to the track width, and included in
Masterlog, PDF, and printing. Existing system interpretation intervals are not deleted and remain
visible outside an overlapping description.

## Curves and missing values

- a real numeric `0` remains zero;
- LAS `NULL`, `NaN`, and infinite values are missing data;
- missing values break the curve;
- separate segments are not connected across a data gap;
- non-positive values are not rendered on a logarithmic scale;
- every curve retains its own range, colour, and linear or logarithmic scale.

## Laptop screens and the inspector

The main window is constrained to the available screen geometry. When the form is wider than the
viewport, the body scrolls horizontally instead of pushing the window beyond the desktop. The
right Inspector panel has a collapse button and can also be hidden from the View menu. User column
widths remain editable and persistent.

## Saving

The diskette action and `Ctrl+S` save the project. Saved state includes lithology intervals, shared
cuttings samples, LBA, calcimetry, rich descriptions, the selected form, and its screen layout. The
factory template is not modified. The diskette does not overwrite LAS; save manual edits after
each work stage. A successful daily append saves `.geologpkg` automatically with a recovery copy
of the previous revision. For daily continuation, see the
[well project workflow](PROJECT_WORKFLOW.md).
- The LBA track now follows the three-subcolumn GeoData working layout: score, fluorescence color and bitumoid type. Ring/spot size reflects intensity 1–5, while the colored interval cell shows LB/MB/MSB/SB/SAB class.
- Technology parameter names are fully localized per language, including torque, hook load and inlet mud density.
