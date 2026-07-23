# Статус проекта

Срез: 23 июля 2026 года. Версия 0.7.32, тестовая сборка.

## Решение о выпуске

Последний полный baseline 0.7.28 зелёный: Ruff проходит, mypy сообщает 0 ошибок в
262 исходных файлах, полный pytest — 1217 пройдено и 10 пропущено. Для 0.7.32 выполнены
`compileall`, сборка wheel и доступная headless-регрессия: 707 тестов пройдено, 4 платформенных
сценария пропущено. Полный сбор pytest останавливается на 95 Qt/LAS-зависимых модулях, потому
что в контейнере нет PySide6, pyqtgraph и lasio; Ruff и mypy также недоступны. Сборка остаётся
тестовой до полного gate и Windows/HiDPI/PDF/физической печати.

## Рабочая основа

- безопасный импорт и редактирование LAS/CSV/TXT/Excel/Paradox;
- проекты с несколькими datasets и индексами, формат проекта v16;
- единый Semantic Channel Dictionary и явный UOM quantity-class dictionary;
- сохранённый semantic binding каждой кривой с исходной мнемоникой, source UOM, sensor,
  confidence и evidence;
- read-only Import Review для индекса, NULL, unresolved, UOM conflict и дубликатов;
- многотрековый планшет, формы, Masterlog, PDF, Print Center, аннотации и project assets;
- синхронные пользовательские документы RU/KK/EN.

Semantic binding создаётся одинаково для CSV/Excel, LAS и Paradox и сохраняется при copy,
merge, resample и TIME↔DEPTH. Старые проекты обогащаются при чтении без перезаписи уже
сохранённой canonical mnemonic.

Следующий срез — интерактивный Import Review с ручными overrides и атомарным подтверждением.

Подробнее: [Semantic Channel Dictionary](SEMANTIC_CHANNEL_DICTIONARY.md),
[аудит](PRODUCT_AUDIT_2026.md) и [план](PROJECT_PLAN.md).
