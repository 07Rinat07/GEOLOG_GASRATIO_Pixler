# Release notes 0.7.41 — typed operational events

- added strict drilling, gas, show, sample, casing, and formation-top payload models;
- added a shared depth/time event envelope with source, revision, calibration, and QC flags;
- implemented deterministic duplicate, out-of-order, gap, stale, and calibration QC;
- added an optimistic-revision `OperationalEventController` and cross-well protection;
- upgraded project format to v17 with a safe v16 → v17 empty-collection migration;
- made the codec reconstruct payloads from the discriminator and reject malformed fields;
- connected EVENTS/DRILLING to exact `ResolvedReportDefinition` bounds without a second resolve;
- removed obsolete import-controller duplicates from `ui`; the active boundary remains in `services`;
- added headless domain, controller, QC, migration, codec, and report tests;
- synchronized plan, status, changelog, and RU/KK/EN guides.

The build remains a test build until the full Ruff/mypy/Qt/LAS gate and Windows smoke tests pass.
