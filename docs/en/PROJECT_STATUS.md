# Current project status

Date: 20 July 2026

The current slice is the **GeoData Depth Workspace**, manual-entry editors based on the supplied
GeoData guide, and unified re-editing of geological intervals.

Completed:

- Geology, Technology, and Gas Data sections aligned with the supplied working screen;
- one depth coordinate and one parameter-header height across all tracks;
- a curated library containing the depth workspace, Masterlog, and time engineering control;
- creation, re-editing, and deletion of lithology;
- one editor for cuttings composition, colour-coded LBA 1–5, calcimetry with automatic residue, and rich description;
- updating the existing record under the same `sample_id` without duplicates;
- an absolute-gas column with `TG_CALC`, `C1`, `C2` and a separate relative-composition column with `C1_REL`–`C5_REL`;
- a fully missing gas sample remains `NULL/NaN` instead of becoming a false zero;
- adaptive main-window geometry, horizontal scrolling, and a collapsible inspector;
- correct curve gaps for NULL/NaN;
- normal save through diskette/`Ctrl+S` and Save As through `Ctrl+Shift+S`;
- synchronized RU/KK/EN documentation and interface strings.

Remaining work: unify screen and print form designers, complete the report-header editor, and finish
automatic Gas Ratio/Pixler interpretation.
