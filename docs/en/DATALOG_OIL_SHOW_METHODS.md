# DataLog / MOL oil shows — recording observations

**Status:** the reference catalogue and read-only completeness audit are developed in a separate PR; there is **no new production DataLog screen yet**. Continue using the existing cuttings/LBA editor; historical LAS and projects are not migrated by this change.

The uploaded `Нефтепроявления_оценки.xls` describes distinct tests; do not merge them into one oil-saturation score:

1. **Odour and visible stain/bleeding (daylight):** distribution, colour and position in pores/fractures.
2. **Direct natural fluorescence (DIF, UV+), before reagent:** fraction of target lithology, distribution, brightness and colour.
3. **Solvent cut:** separately record reaction speed/character, daylight UV− colour, and UV+ colour/brightness.
4. **Post-cut residue:** describe type and colour separately under daylight UV− and ultraviolet UV+.
5. **Florovskaya capillary-extract LBA:** bitumoid group, fluorescence colour and 1–5 semi-quantitative imprint score on filter paper. It is **not** the post-cut residue on a porcelain spot plate.

Current `lba_cut_*` and `lba_residue_*` fields do not store complete UV−/UV+ independent measurements, coverage percentages and each test's brightness. Leave missing measurements unknown. A free-text note can preserve context pending a versioned schema extension, but it is not equivalent to a structured measurement.

Check solvent and mud blanks, spot-plate cleanliness, mud additives, grease, coal/organic matter, mineral fluorescence, washing, sample delay and lag before interpretation. A DataLog oil show alone is not proof of a productive reservoir; combine verified GIS and formation tests.

**Safety:** never use smell to determine H₂S presence; use approved H₂S monitoring and site procedures. Acetone **is miscible with water**, contrary to one statement in the supplied workbook. Perform solvent tests only under site-approved protocols and chemical safety data sheets.

Engineering details and sources: [DATALOG_OIL_SHOW_METHODS.md](../DATALOG_OIL_SHOW_METHODS.md).
