# Files, PDF and engineering calculations

Open the workspace with **Files and calculations** on the main toolbar or with `Ctrl+Alt+F`. A LAS project does not have to be open.

## PDF eraser

1. Open a PDF.
2. Select **Eraser** and choose the square pointer size.
3. Hold the left mouse button and drag the pointer across the page.
4. When the button is released, content under the complete path is removed as one operation.
5. One stroke is reverted by one **Undo** action.
6. Use **Save as** to preserve the source file.

The eraser applies PDF redaction: text, vector content and affected image pixels are removed. It is not a white rectangle drawn over the original content.

## Insert and replace text

**Text** and **Replace text** are separate from the eraser.

1. Select a rectangular area on the page.
2. Choose insertion or replacement.
3. Enter the text.
4. Set the font family, size, bold or italic style, text color, background and alignment.
5. Apply the operation and inspect the result.

A Unicode font is embedded in the PDF, so English, Russian and Kazakh text is preserved correctly. Enlarge the area or reduce the font size when the text does not fit.

## PDF to Word

Two explicit modes are available:

- **Preserve page appearance** inserts every PDF page into DOCX as an image. The appearance is retained, but the page text is not editable.
- **Extract text only** creates editable paragraphs without preserving complex layout, tables or images.

## Archives and logos

The archive page can create, inspect and safely extract ZIP, TAR and formats supported by installed system components. Archive member paths are validated before extraction.

The logo designer provides text, image and font size, colors, background, border and transparency controls, a live preview and raster export.

## Engineering calculations

The general calculator accepts ordinary numbers, decimal dots or commas, mixed fractions such as `7 1/2`, and symbols such as `7½`. The unit converter displays standardized unit symbols.

Additional calculators cover:

- pipe geometry and mass;
- hydrostatic pressure, annular volume and circulation time;
- ECD and drilling-fluid mixing;
- the elevation of a selected depth datum and the bit position.

## Datum elevation and bit position

The former sequential GL, Wellhead, DF, RT and KB form is hidden because it could combine different reference points. The new **Elevations and bit** tab requires one documented depth datum and uses that same datum for every depth input.

### Inputs

- **Ground elevation GL relative to MSL** is the absolute ground-level elevation at the well location relative to mean sea level.
- **Depth reference datum** is the RKB/KB, RT, DF, GL or other point explicitly stated in the drilling report, directional survey or log heading.
- **Datum height above GL** is the vertical offset of the selected point above ground level. Obtain it from controlled rig documentation, an elevation diagram or the approved well header.
- **MD to bit** is measured depth along the well path from the selected datum to the actual bit position.
- **TVD to bit** is true vertical depth from the same datum. For a deviated well, obtain it from the directional survey or trajectory model.

**The full derrick or mast height is not part of this calculation.** Only the selected datum height above GL is used.

### Formulas and sign convention

The application uses one vertical coordinate system:

```text
E_datum = E_GL + H_datum_above_GL
E_bit = E_datum - TVD
TVDSS = TVD - E_datum
Bit_below_GL = TVD - H_datum_above_GL
```

Where:

- `E_GL` is ground elevation relative to MSL, positive upward;
- `E_datum` is the absolute elevation of the selected RKB/KB, RT, DF, GL or other datum;
- `TVD` is vertical depth from the selected datum to the bit, positive downward;
- `E_bit` is absolute bit elevation relative to MSL;
- `TVDSS` is depth below mean sea level, positive downward.

Enable **Vertical well: use TVD = MD** only for a genuinely vertical well or when the source data formally defines TVD as equal to MD. In a deviated well, MD is normally greater than TVD, so the application rejects TVD greater than MD when both use the same datum.

### Example

Ground level is `150 m` above MSL. RT is `7.5 m` above GL. MD to the bit is `3000 m`, while directional-survey TVD is `2500 m`.

```text
RT elevation = 150 + 7.5 = 157.5 m
Bit elevation = 157.5 − 2500 = −2342.5 m
TVDSS = 2500 − 157.5 = 2342.5 m below MSL
MD − TVD = 500 m
```

### Terms

- **DF — Drill Floor** is the rig working platform.
- **RT — Rotary Table** is the rotary table; its elevation equals DF only when the documentation explicitly defines them as equal.
- **RKB/KB — Rotary/Kelly Bushing** is the top of the kelly bushing, commonly used as the zero point for depth.
- **GL — Ground Level** is the ground surface at the well location.

Do not copy an RT, RKB or DF height from another rig, and do not combine a depth measured from one datum with the elevation of another datum.

### Industry sources

- Energistics WITSML, WellElevationCoord: https://docs.energistics.org/WITSML/WITSML_TOPICS/WITSML-500-298-0-R-sv2000.html
- Energistics WITSML, WellDatum: https://docs.energistics.org/WITSML/WITSML_TOPICS/WITSML-500-296-0-R-sv2000.html
- Energistics WITSML, MeasuredDepthCoord: https://docs.energistics.org/WITSML/WITSML_TOPICS/WITSML-500-449-0-R-sv2000.html
- SLB Energy Glossary, true vertical depth: https://glossary.slb.com/Terms/t/true_vertical_depth.aspx
- SLB Energy Glossary, depth reference: https://glossary.slb.com/en/terms/d/depth_reference
- IADC Lexicon, RKB: https://iadclexicon.org/rkb/

## Languages

The interface, help text, confirmations, common errors and this guide are available in Russian, Kazakh and English. Formulas, international abbreviations, file names and user data are not translated.
