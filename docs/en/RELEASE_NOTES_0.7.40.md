# Release notes 0.7.40 — DOCX and HTML

- added one shared document model for DOCX and self-contained HTML;
- both formats use one resolved ReportDefinition, interval, and Coverage snapshot;
- `0`, `—`, and `#N/A` remain distinct engineering states;
- DOCX is safe OOXML with no macros or external embedded objects;
- HTML loads no external scripts or styles;
- output and Passport v4 are written in one recoverable transaction;
- Passport fingerprints the completed DOCX/HTML bytes;
- added localized menu actions and English user documentation;
- project format remains v16.

Checks: 73 passed focused tests; available regression: 926 passed, 4 skipped, 3 LAS scenarios deselected.
