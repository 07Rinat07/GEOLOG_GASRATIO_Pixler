# GEOLOG GASRATIO@Pixler 0.7.93

## Runtime localization of tablet forms

- Switching the application language now retranslates known factory track titles, group headers and parameter captions immediately, without reapplying or recreating the form.
- Examples: `Бурение` → `Бұрғылау` / `Drilling`, `Описание пород` → `Тау жыныстарының сипаттамасы` / `Rock description`, and `Газ C1–C5` → `C1–C5 газы` / `C1–C5 gas`.
- Automatically split LAS columns keep their numeric suffix, for example `Бурение 2` → `Drilling 2`.
- Technology curve labels combine the built-in form dictionary with the Sensors catalog, so standard persisted Russian/English captions no longer block the active-language label.

## Geological labels

- Catalog lithotype names in cursor summaries, cuttings composition and empty rock-description fallbacks now follow RU/KK/EN.
- An exact catalog rock name entered as the description is translated conservatively.
- Free-form geological prose and custom user captions are intentionally preserved unchanged; the application does not silently machine-translate user data.

## Compatibility

- Project format remains `v21`.
- Form schema remains `v11`.
- Tablet layout remains `v21`.
- Canonical startup remains `python -m geoworkbench.app.main`.
