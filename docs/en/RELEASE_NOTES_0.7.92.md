# GEOLOG GASRATIO@Pixler 0.7.92

## Compact tablet column captions

- Long labels such as **Stratigraphy** and **Cuttings log** are drawn as one 90-degree line and the font is fitted automatically so the caption is not clipped.
- The rotated title band increased from 88 to 96 px for stable rendering across Windows fonts and DPI settings.
- **LBA** is horizontal by default in all ready and user forms because the three-letter caption does not need rotation.
- Depth/Time, Stratigraphy, Lithology, Cuttings log and Calcimetry keep their vertical compact presentation.

## Form compatibility

- Project format: `v21`.
- Form schema: `v11`.
- Tablet layout: `v21`.
- Legacy form v8, tablet v18 and 0.7.91 forms are migrated automatically.
- Compact columns retain the 50% width reduction with a 48 px minimum; ordinary curve tracks retain an 80 px minimum.

## Form workflow

**Create form** and **Save user form** are unchanged. The library shows all ready and user form entries; duplicate names are checked after case folding and whitespace normalization.

Canonical startup: `python -m geoworkbench.app.main`.
