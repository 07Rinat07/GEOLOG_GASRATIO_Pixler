# GEOLOG GASRATIO@Pixler 0.7.93

## Form translation on language switch

- Switching Russian, Kazakh or English now updates standard tablet track, group and parameter captions immediately without reapplying the form.
- Examples include `Бурение` → `Бұрғылау` / `Drilling`, `Описание пород` → `Тау жыныстарының сипаттамасы` / `Rock description`, and `Газ C1–C5` → `C1–C5 газы` / `C1–C5 gas`.
- Numeric suffixes of generated columns are preserved, for example `Бурение 2` → `Drilling 2`.
- Technology parameter captions are resolved through the factory-form dictionary and Sensors catalog.

## Rocks

- Catalog rock names follow the active language in cursor summaries, cuttings composition and rock-description fallbacks.
- An exact catalog rock name stored as a description is also shown in the active language.
- Free-form geological descriptions and custom user captions remain unchanged.

## Compatibility

- Project format: `v21`.
- Form schema: `v11`.
- Tablet layout: `v21`.
- Startup command: `python -m geoworkbench.app.main`.
