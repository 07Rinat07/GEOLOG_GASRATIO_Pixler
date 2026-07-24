# Full project manifest — 0.7.58

Base supplied by the user: `GEOLOG_GASRATIO_Pixler(3).zip`, package version 0.7.57.

This archive is a complete project tree, not a patch. Its root contains `src/`,
`tests/`, `docs/`, `resources/`, `pyproject.toml`, and the user-supplied project data.

## Implemented

- dense curve-header viewport is aligned to complete 58 px rows;
- the final parameter row has bottom safety clearance and cannot be cut by the plot boundary;
- more than six parameter rows use visible row-based internal scrolling;
- screen-only curve colours are restrained while persisted/printed colours remain unchanged;
- ordinary thin pens are reduced in multi-curve tracks;
- minor grid lines are lighter and hidden when pixel spacing is unreadable;
- obsolete duplicate UI import-controller modules were removed;
- package version updated to 0.7.58; project format remains v20.

## Verification performed in the build environment

- focused header/screen-style/source-contract tests: 19 passed;
- available headless regression: 1070 passed, 4 skipped;
- `compileall`: passed;
- wheel `geolog_gasratio_pixler-0.7.58-py3-none-any.whl`: built successfully;
- Git overlay verification against the supplied 0.7.57 archive showed real modified,
  added, and deleted files.

PySide6, pyqtgraph, and lasio are not installed in the build container, so Windows
visual smoke testing remains required.
