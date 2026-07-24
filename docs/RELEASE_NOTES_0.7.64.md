# 0.7.64 — form naming reference and compact-column workflow

Version 0.7.64 replaces the small blind name prompt used by **Create form** with a dedicated
reference window. It lists every built-in and user form with search, axis, and origin columns.
Selecting an item shows its description, visible columns and saved widths, track and parameter
counts, and bound mnemonics before the new name is entered.

The new-name field normalizes accidental whitespace and blocks exact duplicates regardless of
letter case or repeated spaces. The user selects Depth or Time in the same window, and an available
name is saved to the user-form repository.

The existing protected template set remains unchanged; a duplicate MASTERLOG template is not added.
Existing compact-column behavior remains:
Stratigraphy, Lithology, Cuttings, Calcimetry, LBA, and Depth use the 40% reduction and 48 px
minimum, while ordinary graph and text tracks retain the 80 px minimum.

RU/KK/EN guides, feature maps, status, plan, testing notes, documentation audit, and regression
coverage are synchronized. Project format remains v20, form schema remains v7, and tablet layout
remains v17. The root README stays concise and unchanged.
