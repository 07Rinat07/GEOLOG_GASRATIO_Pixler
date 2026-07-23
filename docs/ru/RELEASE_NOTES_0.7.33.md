# Примечания к выпуску 0.7.33 — интерактивный Import Review

Дата: 23 июля 2026 года. Статус: тестовая сборка.

## Новое

- единый `ImportReviewDialog` подключён к CSV/TXT, Excel, LAS и GeoScape/Paradox;
- пользователь может выбрать активный индекс, исправить его мнемонику, роль, тип и UOM;
- добавлен дополнительный числовой NULL-сентинел с преобразованием в `NaN` только в принятой копии;
- для каждого канала доступны включение/исключение, canonical mnemonic/kind, quantity class и UOM;
- автоматическое сопоставление Semantic Channel Dictionary можно восстановить одной командой;
- preview показывает NULL, duplicate, gap, order, unresolved, UOM conflict, all-null и duplicate kind;
- блокирующие ошибки отключают подтверждение, предупреждения остаются видимыми;
- принятые ручные решения сохраняются в semantic binding evidence и параметрах dataset.

## Архитектура и безопасность

- `ImportReviewController` формирует initial plan, read-only preview и валидированный commit;
- preview/commit выполняются на глубокой копии и не изменяют loader-owned dataset;
- `DatasetImportJobExecutor` вызывает review до project-session port;
- отмена CSV/Excel/Paradox или отдельного LAS не создаёт dataset/well и не меняет `dirty`;
- пакетный LAS показывает отдельный review для каждого файла;
- изменение UOM является исправлением метаданных, а не скрытой конвертацией значений;
- формат проекта остаётся v16.

## Проверки

- 731 доступный headless/regression/source-integrity тест пройден;
- 4 платформенных сценария пропущено;
- 3 LAS-roundtrip теста требуют `lasio`, 1 Qt-сценарий требует `PySide6`;
- `compileall` выполнен без ошибок;
- полный Ruff, mypy, Qt/LAS pytest и Windows GUI/HiDPI/PDF/physical-print smoke-test нужно повторить в полном окружении.
