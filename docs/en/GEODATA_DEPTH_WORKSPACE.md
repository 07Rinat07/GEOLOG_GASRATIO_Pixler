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

`Shift + left drag` is available in Cuttings, Calcimetry, and LBA tracks. Releasing the mouse in
Cuttings opens the shared sample editor based on the GeoData dialogs. Calcimetry and LBA open
**Sample analysis**. The shared editor has the following fields.

- editable top and bottom;
- up to four rock components;
- a percentage for each rock, with an exact total of `100%`;
- no LBA result or one of `LB`, `MB`, `MSB`, `SB`, `SAB`;
- LBA intensity from 1 to 5;
- optional calcite and dolomite, with a combined maximum of `100%`;
- rich rock/cuttings description;
- interpretation or conclusion.

If the Cuttings selection exactly matches both boundaries of a single saved sample without rock
composition, the shared editor loads its analysis and description. Adding composition keeps the
sample's `sample_id` and saved data. Translation states follow the existing rules for changed fields
and their dependencies. Nearby intervals, an exact match with composition, or multiple exact
matches open an empty editor.

In an empty editor, each unedited boundary keeps the precision of the selection. If the confirmed
top and bottom already belong to a record, saving is blocked. You can adjust the boundaries and save
the new sample in the same dialog. To add composition to an existing sample, select both of its exact
boundaries.

Double-clicking a saved sample opens the editor for that track. Changes in the shared editor
keep the existing `sample_id` and refresh Cuttings, LBA, Calcimetry, and Description together.
Opening the shared editor with a double-click also lets you delete the entire sample.

If a rock description, LBA description or conclusion has both legacy text and a Russian version,
the shared editor preserves both when you add composition or edit other fields. An explicit edit
on a Russian tab updates the corresponding legacy field.

Rock percentages display one decimal place. Each share keeps its stored precision while its
displayed number stays the same. The displayed total and validation use the shares to be saved.
Select **Remainder** to fill the selected rock's share up to a total of 100%, using the exact
shares of the other rocks.

The shared editor, **Sample analysis** and the rock description editor show depths to three decimal
places. When editing a saved sample, each boundary keeps its stored precision while its displayed
value stays the same. Editing one boundary preserves the precision of the other.

When you move a saved sample in any of these editors, another record with the same top and bottom
depths blocks the move, even if it contains only analysis or description. A rejected move leaves
both records intact. A nearby pair with at least one different depth is subject to the composition
overlap rules.

On the tablet, warnings about an occupied interval or overlap with a sample that has rock
composition appear in the interface language. They show both stored depths of the conflicting
sample at their original precision.

When filling in analysis or a description by interval on the tablet or in Masterlog, or when
filling cuttings in Masterlog, a single exact match on both depths takes priority. If there is
no exact match, the application uses the existing lookup tolerance for that command. If several
saved samples match at the first stage that finds any, the application shows a warning and leaves
the records unchanged. Refine both boundaries to select a sample. If several records share the
exact pair, open the intended saved sample directly.

When changing boundaries in **Sample analysis**, you can move a sample with rock composition to
an interval free of other samples with rock composition. Shared endpoints are allowed. An
analysis-only interval can overlap a rock-composition sample if at least one boundary differs.

When you Shift-drag in a Calcimetry or LBA column on the tablet, the sample lookup works as in
Masterlog. It checks for an exact match on both boundaries first, then checks within `0.000001 m`
per boundary and falls back to the existing save tolerance. A matching sample opens with its
recorded values and depths. Saving uses its `sample_id`.

Editing the depths of a loaded sample moves it. After a warning about a rejected move, you can
correct the boundaries and save again in the same dialog. For a new selection, each untouched
boundary keeps its original precision. After you edit the boundaries, both depths must match
exactly to reuse an existing sample.

In Masterlog, use **Fill cuttings** to select an interval, then adjust its top and bottom depths
in the composition dialog if needed. Each unedited boundary keeps the precision of the original
selection. When you edit either boundary, the application matches existing records by both exact
depths. Confirming the original selection allows matching within tolerance.

The command adds rock shares to the matching analysis or description record and keeps its
`sample_id`, exact saved depths, and saved data. The overlap check uses those saved depths.
Adjacent intervals may share a boundary. Reviewed analysis translations keep their status.
A change in composition can mark dependent rock description translations as needing an update.

After a warning about overlap with another sample with composition, an interval that already has
composition, or several matching samples, the same dialog reopens with the exact depths and rock
percentages you entered. Correct the boundaries and save again. Cancelling leaves the project
unchanged. The overlap and already-filled warnings appear in the interface language and show both
stored depths of the conflicting sample at their original precision.

In Masterlog, **Calcimetry / LBA** looks up a sample before opening the dialog. It checks for an
exact match on both boundaries first, then for a match within `0.000001 m` on each boundary and
finally with the existing save tolerance. The matching sample opens with its saved depths,
analysis and conclusion source language, if recorded.

Masterlog saves the boundaries confirmed in the dialog. A boundary left unchanged keeps the
precision of the selection for a new interval or of the saved depth for a loaded sample. Editing
the boundaries moves the loaded sample and keeps its `sample_id`. Masterlog rejects the move if
another record already uses both new boundaries. The warning appears in the interface language and
shows both stored depths of that record at their original precision. If no sample was loaded,
editing the selection requires an exact match to reuse an existing record.

Changing measurements or another language preserves legacy LBA description and conclusion fields
while their Russian versions stay the same. Editing a Russian version updates the corresponding
legacy field.

In **Sample analysis** on the tablet or in Masterlog, the Russian tab may show conclusion text
from a legacy record. To record it as the original, explicitly select Russian in **Conclusion
source language**. If you leave the text unchanged, translation tracking starts with the original
stored text. Other language entries, including `und`, are preserved. Confirming without changes
leaves the legacy conclusion as stored. Source assignment requires text in the chosen version.

To remove a legacy LBA description or conclusion, clear its field on the Russian tab in
**Sample analysis** and save. Other fields and language entries, including `und`, are preserved.
Confirming without edits keeps the stored text. Changes go to the loaded sample. If no rock
composition, description or analysis data remains, the empty record is removed. If the selected
original is left empty, the dialog rejects the save.

In Masterlog, **Cuttings description** opens the version for the interface language. If that
version is missing, the dialog shows available text for reference. Explicit edits are saved in
the interface-language version. Confirming without changes preserves the original formatting,
all language versions and translation revisions. The description is saved on the sample that
the dialog loaded, at its recorded depths even when the match used tolerance. A new record uses
the exact selected depths.

The shared editor and **Sample analysis** show calcite and dolomite to one decimal place. Each
measurement keeps its stored precision while its displayed number stays the same. When you edit
one percentage, the total check uses the other measurement at its stored precision. The shared
editor uses the same values to calculate the residue.

Editing other fields preserves the recorded bitumoid type code and LBA group. Recognized older
codes are shown as the corresponding catalog types. Select a type to update both fields, or
choose **No result** to clear them.

The shared editor preserves form or distribution, solvent-cut type, speed and color, residue type
and color, odour, and stain previously entered in Sample analysis.

## Description editor

A saved sample description is rendered both in the dedicated description track and in the
on-screen and printed column whose system type is Interpretation. Its displayed heading may be
renamed from the context menu or form editor, for example to Cuttings log; the system type and
project compatibility do not change.

In Select mode (`Alt+1`), hold `Shift` and left-drag in an Interpretation or Rock description
track. A dedicated editor opens without requiring rock percentages. Correct the exact top and
bottom, select a RU/KZ/EN language and ready template, or enter arbitrary text. Double-click a
saved description to reopen it. **Delete description** is available when the interface
language has a saved version. The Russian interface can also delete a legacy description without
a language tag. When a version is missing, text from another language is shown for reference.
If a source language is assigned, change it before deleting the original.

Deleting the description preserves composition, LBA, and calcimetry, including a recorded
result of 0% calcite or dolomite in a sample without rock composition. If the interval contains
only a description, deleting its last language version removes the interval. Clearing the last
saved version in the editor and confirming also removes the interval.

For a new interval, each unedited boundary keeps the original precision of the selection. If you
confirm the original selection and it matches a saved sample within the existing tolerance, the
editor saves the description at that sample's recorded depths and keeps its `sample_id` and the
review status of its analysis translations. If you edit either boundary, the editor reuses a
saved sample only when both depths match exactly.

When the active dataset of the same well covers only part of a saved sample interval, you can
edit the description text in Masterlog and edit the text or word wrapping on the tablet. The
edit uses the sample's exact stored depths and `sample_id`. New intervals and changes to the
boundaries must fit the active dataset's depth range.

To move a saved sample, double-click its description and edit the depths. Changing the depths or
word wrapping preserves the original formatting and all language versions. If the editor shows
fallback text from another language or a legacy record, the unedited text stays in its original
field. Text and formatting edits apply to the interface language. When a version is cleared,
the editor checks that text remains in the recorded source language.

Depth changes update the existing translation dependencies. Changing only word wrapping
preserves translation states and language revisions. Confirming without changes leaves the
project clean.

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
