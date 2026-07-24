# 0.7.64 — form-name reference during creation

**Create form** now opens a dedicated window containing every built-in and user form. Search,
name, axis type, and origin are visible. Selecting a form shows its description, visible columns
and saved widths, track and parameter counts, and bound curve mnemonics.

The new name and **Depth** or **Time** axis are entered in the same window. Accidental leading and
trailing whitespace is removed and repeated internal whitespace is collapsed. An exact match with
an existing name is blocked regardless of case or extra spaces.

The existing protected template set remains unchanged; no duplicate MASTERLOG template is added.
The 0.7.63 compact widths remain in place:
Stratigraphy, Lithology, Cuttings, Calcimetry, LBA, and Depth are reduced by 40% and use a 48 px
minimum; ordinary graph and text tracks retain the 80 px minimum.

Documentation, instructions, status, plan, and tests are updated in Russian, Kazakh, and English.
Project format remains v20, form schema remains v7, and tablet layout remains v17.
