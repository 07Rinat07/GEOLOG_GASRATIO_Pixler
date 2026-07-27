# GEOLOG GASRATIO@Pixler 0.7.89

Fixed form application and rollback after opening a new GeoScape2 GS2 dataset.
A form's saved vertical-axis identifier is now validated against the current
dataset. A stale reference falls back to the active axis instead of raising
`NoneType.role`. Absolute-time sources still migrate relative TIME to DATETIME,
while an explicitly selected depth axis is preserved.

Project format remains v21, form schema v9, and tablet layout v19. Existing
factory and user forms remain compatible without migration.
