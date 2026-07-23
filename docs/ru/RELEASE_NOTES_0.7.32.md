# Примечания к выпуску 0.7.32 — Semantic Channel Dictionary

## Что изменено

- добавлены единые `SemanticChannelDictionary` и `UomDictionary` поверх существующего
  Sensors-каталога;
- каждая импортированная кривая получает сериализуемый semantic binding с canonical kind,
  quantity class, UOM, aliases, sensor/source, исходной мнемоникой, confidence и evidence;
- CSV/Excel, LAS и Paradox используют один resolver;
- неизвестные vendor-каналы и единицы остаются явными и не угадываются;
- UOM-конфликт между инженерным типом канала и source unit понижает confidence и выводится
  как ошибка review;
- semantic snapshot сохраняется при copy, transfer, merge, reverse/resample и TIME↔DEPTH;
- добавлена read-only headless-модель Import Review для индекса, NULL, unresolved, UOM и
  duplicate canonical kinds;
- Curve Catalog и dataset JSON export используют сохранённую семантику;
- формат проекта повышен до v16 с безопасной миграцией v15 → v16.

## Совместимость

Старые проекты открываются без потери данных. Если у legacy-кривой нет binding, он создаётся при
чтении с сохранением уже записанной canonical mnemonic. Исходные LAS/DB не изменяются. Layout и
пользовательские сценарии текущего выпуска не менялись.

## Проверка

Доступная headless-регрессия: 707 тестов пройдено, 4 платформенных сценария пропущено;
`compileall` и wheel 0.7.32 завершены без ошибок. Полный Qt/LAS pytest, Ruff, mypy и ручной
Windows/HiDPI/PDF/physical-print gate нужно повторить в установленном окружении.
