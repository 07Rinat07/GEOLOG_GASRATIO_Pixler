# User guide

GEOLOG GASRATIO@Pixler is an editor for drilling, mud-logging, and LAS data.

## Language

Choose Русский, Қазақша, or English on first launch. You can later change the language from
“Language / Язык / Тіл”. Restart the application to update every open window consistently.

## Import

Use “File → Import data...” (`Ctrl+I`) and select LAS, CSV/TXT, or Excel. Source files are
never modified. The CSV/TXT and Excel wizards use the selected language for index, DATE/TIME,
time-zone, preview, and validation controls.

## Table editing

The LAS table supports direct values, constant or noise interval fills, copy/paste, and
Undo/Redo. Every command and selection validation message uses the selected language.

## LAS export

The export dialog configures LAS 1.2/2.0, WRAP, NULL, precision, and custom-section
preservation. Settings, warnings, and overwrite confirmation use the selected language.

## Calculation formulas

Formula Profiles displays the passport, expression, output, source, and input-curve mapping.
DEXP names and descriptions are available in RU/KK/EN; formulas and units are not translated.

The complete engineering documentation currently lives in the parent `docs` directory and
is being migrated into synchronized RU/KK/EN user guides.
