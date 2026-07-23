# Project plan

Current as of 24 July 2026.

## Completed emergency hotfix 0.7.46

- [x] use `Qt.MouseButton.NoButton` in the tablet grid overlay;
- [x] keep imported data accessible when grid/tablet presentation fails;
- [x] open a safe table recovery workspace after successful registration;
- [x] keep Import Review warnings non-blocking;
- [x] capture per-file failures with read/parse/policy/review/register/present stages;
- [x] provide severity, stable code, corrective action, context, exception type, and traceback;
- [x] persist blocking reports and support Copy/Save in the UI;
- [x] preserve duplicate LAS mnemonics by physical column and skip only malformed channels.

Manual exit criterion: reproduce the reported LAS on Windows/PySide6 and confirm that import,
table recovery, tablet first frame, and saved diagnostics work without a black workspace.

## Planned follow-ups

- [ ] read-only offline WITSML 2.1 inventory and mapping fixtures;
- [ ] optional aligned multi-dataset overlays inside one form;
- [ ] directory watcher that proposes detected LAS files and still requires preview confirmation;
- [ ] secured ETP 1.2 only after successful fixture replay.
