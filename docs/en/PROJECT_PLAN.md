# Project plan

Current as of 23 July 2026.

## Completed urgent workflow slice 0.7.45

- [x] per-column grid/ticks independent from hidden renderer axes;
- [x] editable header min/max, caption colour and underline colour;
- [x] complete reusable form layout, viewport, source binding and revision persistence;
- [x] transparent tightly cropped factory gas/drilling symbols;
- [x] multiple independent DEPTH/TIME datasets per well;
- [x] explicit safe daily LAS append with axis/unit/well/schema guards;
- [x] idempotent SHA-256 import, overlap conflict rejection and per-dataset audit history;
- [x] editable 0.2 m default step for new depth LAS.

## Planned follow-ups

- [ ] optional aligned multi-dataset overlays inside one form;
- [ ] directory watcher that only proposes a detected LAS and still requires preview confirmation;
- [ ] offline WITSML 2.1 inventory and mapping fixtures;
- [ ] secured ETP 1.2 only after successful fixture replay.
