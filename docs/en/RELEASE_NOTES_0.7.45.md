# GEOLOG GASRATIO@Pixler 0.7.45 — working forms and daily LAS growth

Test build dated 23 July 2026. Project format v20, form schema v6, tablet layout v15.

- per-column major/minor grid visibility, opacity and print settings;
- curve headers with editable min/max scale, caption colour and underline colour;
- complete reusable form revisions with widths, viewport, scales and curve presentation;
- annotations and symbols remain scoped to the selected dataset and form;
- 19 factory symbols are transparent, tightly cropped PNG assets;
- safe daily append to one explicitly selected DEPTH or TIME dataset;
- strict axis/unit/well/curve-schema checks, idempotent SHA-256 imports and atomic conflict rejection;
- independent append history for every dataset in a multi-dataset well;
- default new depth LAS step is 0.2 m and remains editable;
- automatic v19→v20, form 0–5→6 and layout 1–14→15 migration.
## Verification

- focused forms/grid/symbols/daily-LAS/project/codec: **146 passed**;
- available headless regression: **995 passed, 4 skipped, 3 deselected**;
- the mandatory visual Qt/Windows smoke test remains required before stable.

