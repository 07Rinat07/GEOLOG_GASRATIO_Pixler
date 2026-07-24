# Build manifest 0.7.63

Version 0.7.63 is built from the user's supplied 0.7.62 project archive. Project format remains
v20. Form schema changes from v6 to v7 and tablet layout from v16 to v17. The root `README.md`
remains concise; implementation and verification details stay under `docs`.

## Included changes

- retained the complete multilingual documentation audit from 0.7.62;
- introduced a shared compact-width policy for Depth, Stratigraphy, Lithology, Cuttings,
  Calcimetry, and LBA tracks;
- reduced those built-in defaults by 40% and allowed manual resizing down to 48 px;
- preserved the 80 px minimum for ordinary curve, gas, interpretation, and text tracks;
- migrated legacy user forms and saved tablet layouts once, without repeated shrinking;
- applied the policy to form models, editors, inspectors, mouse resizing, project reopening,
  actual-size preview/PDF/printing, and form-to-MASTERLOG print layout;
- retained the three ready layouts from Form Manager as protected built-in application templates;
- replaced informal form captions with polished RU/KK/EN names;
- synchronized RU/KK/EN guides, feature maps, status, plan, release notes, and tests.

## Verification scope

The package is checked with the independent documentation audit, focused compact-column tests,
available headless regressions, `compileall`, package build, and ZIP integrity verification.
Complete visual mouse-resize, HiDPI, PDF, and physical-printer validation remains a Windows gate
with PySide6, pyqtgraph, and lasio installed.

## Root README policy

The root README does not contain migration internals, detailed bug history, or per-version test
reports. Those details remain in this manifest, release notes, CHANGELOG, and localized guides.
