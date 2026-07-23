# GEOLOG GASRATIO@Pixler 0.7.46 — LAS import recovery and diagnostics

Emergency test build dated 24 July 2026. Project format remains **v20**.

## Fixed regression

The 0.7.45 engineering-grid overlay passed a bare integer `0` to PySide6 instead of the typed
`Qt.MouseButton.NoButton`. Current PySide6 versions could raise during the first tablet render
after LAS parsing, review, and registration had already succeeded. The dataset existed, but the
workspace stayed black.

0.7.46 uses the typed flag, falls back to the axis grid when the overlay fails, and opens a safe
LAS table workspace when tablet/curve presentation cannot be completed. Import Review warnings
remain non-blocking, and unexpected failures are contained per source file instead of escaping
into the Qt event loop.

## Actionable diagnostics

The importer now records stage-aware diagnostics for read, parse, policy, review, registration,
and presentation. Each item includes severity, stable code, source, explanation, corrective
action, context, exception type, and traceback. The report can be copied or saved, and blocking
failures are also persisted atomically in the application data directory.

## LAS resilience

- curve values are read by physical column position, preserving duplicate vendor mnemonics;
- one malformed channel is skipped with a warning instead of rejecting the whole LAS;
- a 9,847-row/73-channel mixed Cyrillic/Latin regression scenario is covered;
- the first default layout remains bounded so a wide LAS cannot overload the initial frame.

## Verification

Project format, form schema, tablet layout, saved forms, symbols, and daily append history are unchanged.

- focused import/recovery/diagnostics: **76 passed**;
- available headless regression: **1011 passed, 4 skipped, 3 deselected**;
- `compileall` passed and wheel 0.7.46 was built successfully;
- PySide6, pyqtgraph, and lasio are unavailable in the container, so a real-LAS Windows/Qt first-frame smoke test remains mandatory before stable.
