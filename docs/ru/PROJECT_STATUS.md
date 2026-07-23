# Статус проекта

Срез: 23 июля 2026 года. Версия пакета: **0.7.45**, тестовая сборка. Project format: **v20**.

## Завершённый срез 0.7.45

- инженерная сетка рисуется overlay-слоем и не исчезает при скрытых осях графика;
- каждая колонка независимо хранит grid X/Y, major/minor divisions, alpha и print-grid;
- шапка показывает название, min/max, единицу и тип шкалы; двойной щелчок открывает настройку;
- цвет кривой, текста шапки и линии под названием сохраняются в layout v15 и form schema v6;
- форма хранит ширины, порядок, viewport, источник, revision и стабильный annotation scope;
- 19 заводских depth symbols преобразованы в прозрачные tightly-cropped PNG;
- ежедневный LAS добавляется append-only в явно выбранный dataset текущей скважины;
- DEPTH/TIME, index type/unit, WELL и curve schema проверяются до изменения данных;
- повторный SHA-256 — no-op, одинаковое перекрытие пропускается, конфликт блокируется атомарно;
- каждый dataset имеет собственный `append_history`; миграция `v19 → v20` не смешивает datasets;
- новый глубинный LAS по умолчанию создаётся с шагом 0,2 м.

## Актуальная рабочая основа

Одна скважина может содержать много независимых DEPTH/TIME/derived datasets. Для каждого dataset
сохраняются свой tablet layout, формы и scope аннотаций. Формы и графические объекты не являются
строками LAS и поэтому не теряются при суточном append.

## Ограничения перед stable

Нужны Windows/HiDPI визуальный smoke-test сетки/шапки/значков, ручной импорт реальных суточных LAS,
полный Qt/LAS/Ruff/mypy gate и проверка физической печати. Автоматический watcher каталога и overlay
нескольких datasets в одной форме остаются будущими отдельными срезами.


## Проверка среза

- focused forms/grid/symbols/daily-LAS/project/codec: **146 passed**;
- доступная headless-регрессия: **995 passed, 4 skipped, 3 deselected**;
- `compileall` выполнен; wheel 0.7.45 успешно собран, все 19 transparent-symbol assets включены.

## Следующий вертикальный срез

Read-only offline WITSML 2.1 inventory и mapping fixtures. Сетевой ETP 1.2 остаётся заблокирован до
успешного fixture replay.
