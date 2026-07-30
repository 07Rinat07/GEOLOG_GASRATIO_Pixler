# Files / PDF / Engineering workspace guide

Full user instructions are maintained as synchronized language documents:

- [Русский](ru/FILES_WORKSPACE.md)
- [Қазақша](kk/FILES_WORKSPACE.md)
- [English](en/FILES_WORKSPACE.md)

This summary records the common operating rules that must remain identical in all three versions.

## PDF editing

- The square eraser applies PDF redaction; it does not merely draw a white overlay.
- One continuous eraser stroke is one undo operation.
- **Text** inserts formatted Unicode text into a selected rectangle.
- **Replace text** redacts the selected rectangle before inserting the replacement.
- Use **Save as** to preserve the source PDF.

## PDF to Word

- **Preserve page appearance** inserts rendered PDF pages as images. Layout is preserved and page text is not editable.
- **Extract text only** creates editable paragraphs without claiming to preserve complex layout.

## Well datum and bit position

The old sequential GL/Wellhead/DF/RT/KB form is hidden. The active calculator uses one documented depth datum consistently.

```text
E_datum = E_GL + H_datum_above_GL
E_bit = E_datum - TVD
TVDSS = TVD - E_datum
Bit_below_GL = TVD - H_datum_above_GL
```

Common rules:

- Ground elevation is relative to mean sea level.
- Datum height is the vertical offset of the selected RKB/KB, RT, DF, GL or custom reference above ground.
- The total derrick or mast height is not used.
- MD is measured along the well path from the selected datum to the bit.
- TVD is vertical depth from the same datum to the bit.
- `TVD = MD` is valid only for a vertical well or when explicitly defined by controlled source data.
- A deviated well requires TVD from a directional survey or trajectory model.
- Never combine depth from one datum with elevation from another datum.

## Industry references

- Energistics WITSML, WellElevationCoord: https://docs.energistics.org/WITSML/WITSML_TOPICS/WITSML-500-298-0-R-sv2000.html
- Energistics WITSML, WellDatum: https://docs.energistics.org/WITSML/WITSML_TOPICS/WITSML-500-296-0-R-sv2000.html
- Energistics WITSML, MeasuredDepthCoord: https://docs.energistics.org/WITSML/WITSML_TOPICS/WITSML-500-449-0-R-sv2000.html
- SLB Energy Glossary, true vertical depth: https://glossary.slb.com/Terms/t/true_vertical_depth.aspx
- SLB Energy Glossary, depth reference: https://glossary.slb.com/en/terms/d/depth_reference
- IADC Lexicon, RKB: https://iadclexicon.org/rkb/
