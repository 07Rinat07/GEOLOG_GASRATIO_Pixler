# Build manifest 0.7.62

Version 0.7.62 is built from 0.7.61 as a multilingual documentation audit and verification
increment. Project format v20, form schema v6, and tablet layout v16 are unchanged. The root
`README.md` is byte-for-byte unchanged; detailed documentation remains under `docs`.

## Changed areas

- added synchronized `FEATURES.md` maps in `docs/ru`, `docs/kk`, and `docs/en`;
- expanded the three user guides with the shared project-save and export boundary;
- expanded annotation instructions with symbol saving, reopen verification, Undo/Redo, delete,
  lock, print flag, PDF, and project-owned image behavior;
- synchronized LAS Editor, Constructor, lag/depth correction, Report Passport, and SKF import
  instructions where older KK/EN documents were materially shorter than RU;
- updated current status, plan, release notes, testing gate, requirements, roadmap, changelog, and
  documentation policy;
- added `tools/check_documentation.py`, which has no Qt dependency;
- added documentation regression tests and replaced the stale literal version test with a
  pyproject-to-runtime version contract;
- raised package metadata to 0.7.62 without changing persisted schemas.

## Verification

- documentation audit: passed;
- localized Markdown files: **82 per language**, identical filename set;
- interface localization catalogs: **1881 keys per language**, identical key set;
- relative Markdown links: passed;
- current localized guide structure/size parity: passed;
- package/release version contract: passed;
- `python -m compileall -q src tests tools`: passed;
- available headless regression: **1103 passed, 4 skipped, 3 deselected**;
- full test collection is blocked by **82 modules** that require unavailable PySide6,
  pyqtgraph, or lasio;
- the internal package index did not provide those dependencies, so full Qt/UI, real LAS, PDF,
  HiDPI, and physical-printer verification remains mandatory on the supported Windows environment.

## Root README policy

The root README SHA-256 remains
`4a0aca9d53cd74ce4a1b394380fc0db103bbd2cec8c132e5bd880090d72daa5f`. Release details,
test counts, and technical implementation notes remain in `docs`, CHANGELOG, and release notes.

## SHA-256 of key files

```text
4a0aca9d53cd74ce4a1b394380fc0db103bbd2cec8c132e5bd880090d72daa5f  README.md
ad987707e7241c62cace36ce9c39e99127efa036bbf8f7736545950c413aa524  pyproject.toml
fa5534979fa921aee29cf441fbb8f36e41fdd047f5dabf6ea4c029b76f46ecd9  src/geoworkbench/__init__.py
96ecee0699361e851b3d5fd4e201fc73fc8a02c493c9ba82a6603842e985e611  tools/check_documentation.py
73f0aaaebf5678c2432c87ec356117d1b06cba992ca36234228ae13dbdf3410a  tests/test_documentation_sync_0762.py
278922ea8ec9e47eac45df695bb45a971befedf19c7eabb7ce4b954f9f8d705e  tests/test_version.py
738cbf6595d4b1c94dac638bb74b2c3c4fd9909b32333b97bc30368acb3705d4  docs/ru/FEATURES.md
2742fbc077d3d0c1f42b02a591382168b0d9a6737c91da9285a8c66184f05337  docs/kk/FEATURES.md
445d1290bcd3ca52e2723859e11447ffc866e5c40a44b5a600de6781f229302e  docs/en/FEATURES.md
817c9103733d6c8e77bb5e1bfc5a3af52effcccf587e85c1a754432a575dfd6a  docs/ru/ANNOTATIONS.md
67b054ac62e63ca21015611643b9e121c02393931d6cc4474e167e4dfeb99c6d  docs/kk/ANNOTATIONS.md
e5287b8aa5fc5e1599ab7fd00b6b81e14540a83db1227f6015e8e2a83b97afc1  docs/en/ANNOTATIONS.md
```
