# GEOLOG GASRATIO@Pixler project status

Snapshot: 25 July 2026. Package version: **0.7.67**. Project format: **v20**,
form schema: **v8**, tablet layout: **v18**.

## Completed in 0.7.67

- removed the duplicated generic **Scale** caption from every numeric curve header;
- labelled the engineering ruler with the parameter name and unit, for example
  **Weight on bit · t**;
- removed the separate title row, reducing one complete parameter block from 58 to 44 px and
  saving about 24% of vertical header space;
- retained minimum/unit/maximum, automatic range, settings, ticks, and mandatory endpoints;
- applied the layout through the shared `TabletTrackWidget` to every factory, ready, and user form
  without changing project format, form schema, or tablet layout;
- synchronized instructions and release notes in Russian, Kazakh, and English.

## Retained from 0.7.66

The unified full form catalog, responsive top toolbars, safe diagnostics cleanup, bounded import
report retention, complete save dialog, and compact geology-column migration remain unchanged.

## Verification

Regression coverage checks 44 px geometry, parameter-name ruler captions, removal of the legacy
**Scale** key, preserved `A`/`⚙` controls, and RU/KK/EN documentation. Full visual Qt/UI verification
requires Windows with PySide6 and pyqtgraph.
