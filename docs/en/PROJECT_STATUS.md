# Project status

24 July 2026 corrective build: package **0.7.59**, project format **v20**, form schema **v6**, tablet layout **v16**.

## Completed in 0.7.59

- fixed the diagnostic traceback where `TabletTrackWidget` had no `_localizer`;
- every rendered track receives the active `TabletView` localizer before its header is populated;
- direct/plugin construction uses a safe Russian fallback localizer;
- dense forms with more than six curve rows can build localized overflow hints without `AttributeError`;
- transactional form rollback still preserves the last successful layout;
- added source-contract and Qt regression tests for dense localized form switching.

## Verification

`compileall` and available pure/source-contract tests were executed in the container. A Windows/PySide6 smoke test remains mandatory: switch repeatedly between forms containing 7–12 parameters in one track under RU/KK/EN.

## Next vertical slice

Read-only offline WITSML 2.1 inventory and mapping fixtures.
