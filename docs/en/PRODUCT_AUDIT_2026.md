# Product audit and improvements

Current audit dated 23 July 2026: [full engineering report](../PRODUCT_AUDIT_2026.md).

## Current strengths

- safe LAS opening, editing, and export to new copies;
- a synchronized multi-track tablet and interval geology;
- editable Masterlog forms and a screen-independent print renderer;
- configurable major and minor grids for screen and print;
- project forms, lithotypes, annotations, and legacy project migrations.

## What is addressed first

1. The complete test suite, Ruff, and mypy must pass.
2. The tablet and main window will be split into smaller controllers.
3. Channels will receive canonical kinds, units, source, and quality flags.
4. Every report will carry a source, calculation, form, and print passport.
5. WITSML 2.1/ETP 1.2 will follow stabilization in stages: inventory first,
   recorded replay second, and a secured live connection last.

See the [project plan](PROJECT_PLAN.md) for sequencing and the
[project status](PROJECT_STATUS.md) for current limitations.
