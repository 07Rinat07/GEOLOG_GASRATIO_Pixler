# Project plan

Current on 24 July 2026. Hotfix **0.7.59** keeps project format v20, form schema v6, and tablet layout v16.

## P0 — hotfix 0.7.59: safe switching of dense localized forms

- [x] initialize a localizer in every `TabletTrackWidget`;
- [x] pass the active `TabletView` localizer to every new rendered track;
- [x] keep a safe fallback for direct test/plugin widget construction;
- [x] cover the track-creation boundary with a source-contract test;
- [x] add a Qt regression test for a seven-parameter form and overflow tooltip;
- [x] synchronize status, changelog, testing, and RU/KK/EN release notes;
- [ ] Windows/PySide6: repeatedly switch dense forms under RU/KK/EN and verify rollback.

Exit criterion: a form with an internally scrollable header applies without `AttributeError`, while any unrelated failure preserves the previous working form.

## Next stages

- [ ] read-only offline WITSML 2.1 inventory and mapping fixtures;
- [ ] alignment-controlled multi-dataset overlays in one form;
- [ ] directory watcher with preview confirmation for daily growth;
- [ ] secured ETP 1.2 only after successful fixture replay.
