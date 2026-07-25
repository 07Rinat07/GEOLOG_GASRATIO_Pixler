# Build manifest — GEOLOG GASRATIO@Pixler 0.7.67

## Package identity

- Package: `geolog-gasratio-pixler`
- Package version: `0.7.67`
- Project format: `v20`
- Form schema: `v8`
- Tablet layout: `v18`

## Included change

- Numeric curve rulers are labelled by the localized parameter name and unit.
- The redundant generic `Scale` caption and duplicated curve-title row are removed.
- Complete parameter-row height is reduced from 58 px to 44 px.
- Minimum/unit/maximum controls, automatic range, settings, mandatory endpoint labels, and ticks remain.
- The shared renderer applies the layout to factory, ready, and user forms without migration.

## Documentation contract

- `docs/ru`, `docs/kk`, and `docs/en` contain 87 matching Markdown files each.
- Interface localization catalogs contain 1886 matching keys each.
- Current release notes, user instructions, feature maps, Tablet Engine, workspace, status, and plan
  describe the compact parameter-labelled ruler workflow in all three languages.
- The root `README.md` was not changed; SHA-256 remains
  `4a0aca9d53cd74ce4a1b394380fc0db103bbd2cec8c132e5bd880090d72daa5f`.

## Verification

- Focused 0.7.67 geometry, source-contract, localization, and documentation tests: passed.
- Broad available test run: 1149 passed and 4 skipped.
- Three LAS-dependent scenarios could not run because `lasio` is unavailable.
- Eighty-five Qt/pyqtgraph test modules could not be collected because `PySide6` and
  `pyqtgraph` are unavailable in the container.
- `python -m compileall` for `src`, `tests`, and `tools`: passed.
- Documentation audit: passed.
- Wheel `geolog_gasratio_pixler-0.7.67-py3-none-any.whl` built successfully with
  `pip wheel --no-build-isolation`; SHA-256:
  `70c374b15a1b0718111de3a8b15867b60f3fcfa088077e3d97cb74ff82ae05ab`.
- Wheel ZIP integrity check: passed.

Full visual verification of the 44 px Qt header at Windows display scaling still requires the
runtime environment with PySide6 and pyqtgraph.
