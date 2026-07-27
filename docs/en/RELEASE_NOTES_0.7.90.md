# GEOLOG GASRATIO@Pixler 0.7.90

## Documentation and startup

The canonical startup command is `python -m geoworkbench.app.main`. It is now identical in the root
README, the Russian, Kazakh, and English guides, and the active test gate. Obsolete old-version
blocks were removed from user README files, and the documentation index now points to build 0.7.90.

## Tests

A static module-entry-point regression test was added, the documentation audit was extended, and
`docs/TESTING.md` now defines quick, full, and manual Windows GUI gates. Project v21, form v9, and
tablet v19 formats are unchanged.

The project test runner now explicitly loads `pytest_asyncio.plugin`, while a separate headless runner executes every available test and never hides unknown collection failures.
