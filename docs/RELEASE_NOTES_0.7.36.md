# Примечания к выпуску 0.7.36 — Unified ReportDefinition

Дата: 23 июля 2026 года. Статус: тестовая сборка.

## Реализовано

- добавлена immutable `ReportDefinition` schema v1 с профилями geology, cuttings, calcimetry,
  LBA, gas, drilling, events, Masterlog, view и combined;
- добавлен единый resolver full/current/custom/selection для числовых и datetime-индексов;
- preview и итоговый Print Center job используют один зафиксированный interval/index;
- Print Center получил режим выбранного интервала;
- Masterlog preview, PDF и system preview используют одну definition;
- CSV/XLSX выбранного интервала используют один resolved report вместо отдельных границ;
- Report Passport хранит canonical definition payload и digest;
- расчёт depth-row selection и базовая локализация освобождены от лишнего top-level Qt import;
- формат проекта остаётся v16.

## Совместимость

Старые формы, layouts и проекты не требуют миграции. Сохранённые настройки Print Center
продолжают работать; режим selection автоматически недоступен без подходящего выделения.

## Подтверждённая проверка

- 50 целевых тестов ReportDefinition/export/passport пройдено;
- 865 тестов доступной регрессии пройдено, 4 пропущено, 3 LAS-теста исключены;
- `compileall` завершён без ошибок; wheel 0.7.36 собран, metadata проверена.

## Проверка

Финальные результаты автоматических проверок зафиксированы в `PROJECT_STATUS.md` и
`TESTING.md`. Полный Qt/LAS/Ruff/mypy gate и Windows/HiDPI/PDF/physical-print smoke-test
остаются обязательными перед stable.
