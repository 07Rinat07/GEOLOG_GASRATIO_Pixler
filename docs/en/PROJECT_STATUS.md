# Project status

24 July 2026 emergency test build: package **0.7.46**, project format **v20**.

Completed hotfix: corrected the PySide6 grid-overlay mouse-button type; presentation failures no longer hide an already imported LAS; safe table recovery is available; Import Review warnings remain non-blocking; stage-aware actionable diagnostic reports can be copied, saved, and are automatically persisted for blocking failures; duplicate mnemonics are read by physical column position and isolated malformed channels no longer reject the entire source.

Project format v20, form schema v6, tablet layout v15, multi-DEPTH/TIME datasets, saved forms, symbols, annotations, curve settings, and daily LAS append contracts are unchanged.

Verification: **76 focused passed**; available headless regression **1011 passed, 4 skipped, 3 deselected**; `compileall` passed and wheel 0.7.46 built. PySide6, pyqtgraph, lasio, Ruff, and mypy are unavailable in the container, so the real-LAS Windows/HiDPI first-frame smoke test and full installed gate remain mandatory.

Next slice after Windows confirmation: read-only offline WITSML 2.1 inventory and mapping fixtures.
