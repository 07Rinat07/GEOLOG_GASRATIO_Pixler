# Exporting a selected interval to DOCX and HTML

Version 0.7.40 adds two formats to the **File** menu:

- **Export selection to DOCX** — an editable Microsoft Word document;
- **Export selection to HTML** — one self-contained browser and print file.

## Export workflow

1. Open a dataset.
2. Select a depth interval in the chart or table.
3. Select the required curves.
4. Choose DOCX or HTML from **File**.
5. Choose a file name and confirm replacement when required.

Both formats use exactly the same resolved interval as CSV and XLSX. The application does
not read the viewport again and does not silently switch to another index.

## Document contents

- dataset and report name;
- exact bounds and sample count;
- ReportDefinition SHA-256;
- channel coverage table;
- selected-interval data table.

Symbols:

- `0` — an observed zero;
- `—` — a missing sample;
- `#N/A` — the requested channel is unavailable in the dataset.

HTML requires no network connection and loads no external scripts or styles. DOCX contains
no macros or external embedded objects.

A `*.report-passport.json` sidecar is written next to the file. It stores the completed
DOCX/HTML size, MIME type, and SHA-256. Passport verification detects any later modification.
