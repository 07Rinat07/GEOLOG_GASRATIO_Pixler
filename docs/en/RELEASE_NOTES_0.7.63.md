# 0.7.63 — compact geology columns and embedded user MASTERLOG form

Version 0.7.63 frees more horizontal tablet space without narrowing ordinary curve graphs or text
columns. In every built-in depth form, the default widths of **Stratigraphy**, **Lithology**,
**Cuttings log**, **Calcimetry**, **LBA**, and **Depth** are reduced by 40%. These kinds allow a
48 px minimum, while curve and text columns retain the 80 px safety minimum.

Legacy user forms and saved tablet layouts migrate automatically when opened. Only the listed
geological columns are compacted; curve and text widths remain unchanged. Saving writes form
schema v7 and tablet layout v17, so the same form is not reduced again on later opens.

The validated user layout is included as the protected built-in
**MASTERLOG — geological and geochemical form** template. Users create an editable copy while the original
application template remains unchanged. Actual-size printing preserves saved compact proportions;
Fit columns can redistribute widths for the selected paper.

The RU, KK, and EN guides now explain widths, manual resizing, migration, saving and reopening,
printing, and the embedded user template consistently. Regression tests cover width limits,
factory forms, legacy user forms, layout migration, and the MASTERLOG template.

Project format remains v20. Form schema is raised from v6 to v7 and tablet layout from v16 to v17.
The root README remains concise and unchanged.
