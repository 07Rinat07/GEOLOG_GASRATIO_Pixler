# Жоба күйі

Кесім: 2026 жылғы 23 шілде. Package нұсқасы: **0.7.44**, тесттік жинақ. Project format: **v19**.

Соңғы толық расталған baseline — 0.7.28: Ruff таза, 262 source file үшін mypy 0 error, толық
pytest нәтижесі 1217 passed және 10 skipped. 0.7.44 үшін осы контейнерде `compileall`, 72 focused
tests және қолжетімді headless regression орындалды: 987 passed, 4 skipped, 3 deselected. Толық
Qt/LAS/Ruff/mypy gate үшін PySide6, pyqtgraph, lasio, Ruff және mypy қажет. Stable алдында
Windows/HiDPI/PDF/physical-print smoke-test міндетті.

0.7.44 immutable lag correction profile/revisions, constant-time, annular-volume/flow,
pump-strokes және manual control points әдістерін, әр revision үшін бөлек derived dataset,
source/corrected depth осьтерін, explicit time aggregation, provenance fingerprints, tamper checks,
optimistic revision guards, Qt workflow және `v18 → v19` migration іске асырады.

Ағымдағы негізде typed operational events, deterministic QC, append-only acquisition,
checkpoints/replay, versioned lag/depth projections, ReportDefinition v2, Coverage v1, Report
Passport v4 және PDF/XLSX/CSV/TSV/DOCX/HTML adapters бар.

Келесі кесім: read-only offline WITSML 2.1 inventory және mapping fixtures. Fixture replay сәтті
өтпейінше network ETP 1.2 client қосылмайды, credentials project JSON ішінде сақталмайды.
