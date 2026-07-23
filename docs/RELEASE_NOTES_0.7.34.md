# Примечания к выпуску 0.7.34 — Report Passport

Дата: 23 июля 2026 года. Статус: тестовая сборка.

## Новое

- добавлен детерминированный `ReportPassport` schema v1 с каноническим JSON и SHA-256;
- паспорт фиксирует source fingerprints, точный интервал, выбранные значения каналов,
  полный semantic binding/UOM, версии формул, revision формы, язык и render settings;
- channel fingerprints охватывают только отсчёты фактического интервала отчёта;
- формы и tablet layouts получают content-addressed revision, Masterlog сохраняет явную version;
- абсолютный output path и время генерации не входят в паспорт;
- `load_report_passport()` обнаруживает изменение подписанного JSON.

## Экспорт

- Print Center создаёт `<output>.passport.json` для PDF и постраничных изображений;
- прямой экспорт активной визуализации в PNG/SVG/PDF создаёт тот же sidecar;
- Masterlog PDF и интерпретационный PDF создают паспорта;
- физическая печать вычисляет и показывает digest без sidecar;
- существующий sidecar участвует в подтверждении перезаписи.

## Источники и безопасность

- используется import-time LAS fingerprint, embedded lossless LAS либо fingerprint доступного
  внешнего файла с явным предупреждением;
- normalized report-data fingerprint включается всегда;
- sidecar записывается атомарно через временный файл, `fsync` и `os.replace`;
- формат проекта остаётся v16.

## Проверки

- 742 доступных headless/regression/source-integrity теста пройдено;
- 4 платформенных сценария пропущено;
- ещё 4 LAS/Qt-сценария исключены из доступного запуска из-за отсутствующих зависимостей;
- `compileall` выполнен без ошибок;
- полный Ruff/mypy/Qt/LAS gate и Windows/HiDPI/PDF/physical-print smoke-test требуется
  повторить в полном окружении.
