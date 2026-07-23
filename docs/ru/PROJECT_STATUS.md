# Статус проекта

Срез: 23 июля 2026 года. Версия пакета: **0.7.44**, тестовая сборка. Project format: **v19**.

## Решение о выпуске

Последний полностью подтверждённый автоматический baseline 0.7.28: Ruff чист, mypy — 0 ошибок
в 262 исходных файлах, полный pytest — 1217 passed и 10 skipped. Для 0.7.44 в текущем контейнере
выполнены `compileall`, 72 focused tests и доступная headless-регрессия: 987 passed, 4 skipped,
3 deselected. Полный Qt/LAS/Ruff/mypy gate требует `PySide6`, `pyqtgraph`, `lasio`, Ruff и mypy.
Windows/HiDPI/PDF/physical-print smoke-test также остаётся обязательным перед stable.

## Завершённый срез 0.7.44

- immutable `LagCorrectionProfile` и непрерывные revisions;
- методы constant-time, annular-volume/flow, pump-strokes и manual control points;
- отдельный derived dataset на каждую revision, без изменения acquisition dataset/journal;
- source и corrected DEPTH indexes в одной проверяемой проекции;
- explicit repeated-time aggregation и `NaN` вместо скрытой экстраполяции;
- source-prefix, output и acquisition provenance fingerprints;
- проверка tampering/divergence при загрузке project format v19;
- optimistic guards для add/activate revision;
- Qt-окно в меню «Расчёты» с выбором кривых, preview и source/corrected axis;
- ReportDefinition использует явно выбранный active index derived dataset;
- безопасная миграция `v18 → v19` с пустым `lag_correction_profiles`.

## Актуальная рабочая основа

- package 0.7.44; project format v19; acquisition/event/lag schemas v1;
- трёхсекундное неблокирующее приветственное окно;
- Semantic Channel Dictionary и Import Review;
- operational events и deterministic QC;
- append-only acquisition, checkpoints, rollback и replay;
- versioned lag/depth correction с reversible projections;
- ReportDefinition schema v2, Coverage schema v1 и Report Passport schema v4;
- recoverable output transaction и PDF/XLSX/CSV/TSV/DOCX/HTML adapters.

## Следующий вертикальный срез

Read-only offline WITSML 2.1 inventory и mapping fixtures. До успешного fixture replay сетевой
ETP 1.2 client и хранение credentials в проекте не добавляются.
