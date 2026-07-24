# 0.7.63 — compact geology columns and polished built-in forms

Version 0.7.63 gives drilling and gas graphs more horizontal space on the tablet. In every built-in
form, the default widths of Stratigraphy, Lithology, Cuttings log, Calcimetry, LBA, and Depth are
reduced by 40%. These track kinds can be resized down to 48 px; ordinary curve, gas,
interpretation, and text tracks retain the safer 80 px minimum.

The three ready forms already shown in Form Manager remain protected application templates and
receive clear localized names in Russian, Kazakh, and English:

- Integrated mud logging form — geology, drilling and gas;
- MASTERLOG — geological and geochemical form;
- Engineering and drilling monitoring — time form.

Legacy user forms and saved tablet layouts migrate once when opened. Only the requested compact
track kinds are reduced; curve and text widths are preserved. Saving writes form schema v7 or
tablet layout v17, so the same form is not reduced again. Actual-size preview, PDF, and printing
preserve saved proportions, while Fit columns may redistribute widths for the selected paper.

The complete 0.7.62 documentation audit is retained: matching RU/KK/EN document sets, feature
maps, graph-symbol save/reopen instructions, internal-link checks, i18n-key parity,
`tools/check_documentation.py`, and the package-version contract test. The root README remains
concise and unchanged.

Project format remains v20. Form schema changes from v6 to v7 and tablet layout from v16 to v17.
