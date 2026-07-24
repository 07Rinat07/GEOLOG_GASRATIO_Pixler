# Project plan

Current as of 24 July 2026. Hotfix 0.7.51 keeps project format v20, form schema v6 and tablet
layout v16. After Windows verification, the next domain slice is read-only offline WITSML 2.1
inventory and mapping fixtures.

## P0 — hotfix 0.7.51: diagnostics and safe pencil lifecycle

- [x] write rotating UTF-8 logs in the application data directory;
- [x] record uncaught Python/thread exceptions with full tracebacks;
- [x] capture Qt messages and exceptions escaping Qt event handlers;
- [x] log form apply/preview/rollback, tablet render and curve-pencil commit events;
- [x] add commands to open logs, copy the current path and build a diagnostics ZIP;
- [x] exclude LAS values, project assets and saved forms from the diagnostics ZIP;
- [x] refresh only affected curve tracks after pencil edits instead of full rebuild;
- [x] preserve column widths, scroll position and unrelated form widgets after a stroke;
- [x] disable pencil mode and clear stale targets before every full rebuild;
- [x] validate a candidate form model before ending pencil mode and replacing widgets;
- [x] cover logging, bundle privacy and lifecycle contracts with headless tests;
- [ ] run Windows/PySide6 smoke tests: drawing in several columns, Undo/Redo and at least 20 form
  switches immediately after a stroke without layout damage or Qt lifecycle errors.

0.7.51 exit criterion: drawing does not change form topology or widths; form switching remains
usable; every failure can be delivered as one diagnostics ZIP with traceback and event sequence.

## Next stages

- [ ] read-only offline WITSML 2.1 inventory and mapping fixtures;
- [ ] alignment-controlled multi-dataset overlays in one form;
- [ ] directory watcher with preview confirmation for daily growth;
- [ ] secured ETP 1.2 only after successful fixture replay.
