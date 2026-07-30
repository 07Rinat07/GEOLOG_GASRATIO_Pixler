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
- absolute elevations of geological boundaries;
- rig elevation references.

### DF, RT and KB/RKB

- **DF — Drill Floor**: the rig working platform.
- **RT — Rotary Table**: separate equipment located on the drill floor.
- **KB/RKB**: the top of the kelly bushing above RT, often used as a depth datum.

Enter `0` for RT above DF when the documentation defines the DF and RT elevations as equal. Use values from the rig documentation, elevation diagram or log header.

## Languages

The interface, help text, confirmations, common errors and this guide are available in Russian, Kazakh and English. Formulas, international abbreviations, file names and user data are not translated.
