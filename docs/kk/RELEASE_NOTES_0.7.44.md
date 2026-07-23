# 0.7.44 — нұсқаланатын lag/depth түзетуі

Тесттік жинақ. Project format v19; lag correction schema v1.

- immutable correction profile және үздіксіз revisions;
- constant-time, annular-volume/flow, pump-stroke және manual control-point әдістері;
- әр revision үшін source/corrected depth осьтері бар бөлек derived dataset;
- acquisition dataset және append-only journal өзгермейді;
- source-prefix/output fingerprints және жүктеу кезіндегі replay verification;
- formula, parameters, indexes, curves, author, timestamp және acquisition provenance;
- optimistic add/activate guards және бұрынғы revision-ға қайту;
- preview және source/corrected axis таңдауы бар RU/KK/EN Qt workflow;
- қауіпсіз `v18 → v19` migration.

Тексеру: 72 focused passed; headless regression 987 passed, 4 skipped, 3 deselected.
Толық Qt/LAS/Ruff/mypy және Windows smoke gate осы контейнерде орындалмады.
