# Project plan

Current as of 24 July 2026.

## Completed corrective hotfix 0.7.47

- [x] normalize mixed DB index order in the accepted copy only;
- [x] apply one stable permutation to every index and curve;
- [x] expose `index-sorted-copy` diagnostics;
- [x] prefer explicit DEPT/DEPTH/MD for batch DB → LAS while preserving ambiguity safety;
- [x] honor saved profiles and sort before LAS round-trip;
- [x] edit manual min/max directly in ordinary curve headers;
- [x] persist auto/manual range and header colors in the working form;
- [ ] Windows smoke-test D1174.db, BLData.db, batch conversion, and narrow headers.

## Planned follow-ups

- [ ] read-only offline WITSML 2.1 inventory and mapping fixtures;
- [ ] optional aligned multi-dataset overlays inside one form;
- [ ] directory watcher with preview confirmation;
- [ ] secured ETP 1.2 only after successful fixture replay.
