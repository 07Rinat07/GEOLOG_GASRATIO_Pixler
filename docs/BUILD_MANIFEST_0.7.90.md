# Build manifest — GEOLOG GASRATIO@Pixler 0.7.90

## Package

- Package version: `0.7.90`
- Python: `>=3.11`
- Canonical startup: `python -m geoworkbench.app.main`
- Project format: `v21`
- Form schema: `v9`
- Tablet layout: `v19`

## Increment

- current root and RU/KK/EN startup documentation;
- one active `docs/TESTING.md` release gate;
- current-build navigation in `DOCUMENTATION_INDEX.md`;
- automatic startup-command and current-documentation audit;
- static module-entry-point and isolated-runner regression tests;
- explicit pytest-asyncio loading while global plugin autoload is disabled;
- safe reduced-environment test runner;
- project-controller ownership of acquisition dataset selection and dirty state;
- synchronized status, requirements, roadmap, changelog, release notes, and documentation policy.

## Validation performed in the available container

- `python -m compileall -q src tests tools scripts` — passed;
- `python tools/check_documentation.py` — passed: 118 localized Markdown files per language and
  2228 synchronized i18n keys;
- startup/documentation/project-boundary focused tests — 80 passed;
- isolated async runner check — 15 passed;
- `python scripts/run_headless_tests.py` — 1369 passed, 15 skipped;
- headless collection excluded 83 files only because PySide6, pyqtgraph, or lasio were not
  installed in the container.

## Validation not performed in this container

- unfiltered full Qt/GUI pytest suite;
- actual startup of the PySide6 application;
- Ruff and mypy, because those tools were not installed;
- Windows external-monitor, DPI, PDF, and physical-printer acceptance.

These checks remain mandatory before declaring a stable Windows build. The reduced-environment
runner is not a substitute for the full release gate.

## Artifacts

- Source archive: `GEOLOG_GASRATIO_Pixler_0.7.90_DOCUMENTATION_TESTS_SYNCED.zip`
- SHA-256: `GEOLOG_GASRATIO_Pixler_0.7.90_DOCUMENTATION_TESTS_SYNCED.zip.sha256`
- Technical report: `HOTFIX_REPORT_0.7.90.md`
