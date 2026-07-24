# Report Passport

Статус: реализовано с версии 0.7.34. Coverage добавлен в schema v2, печатная модель — в schema v3,
а fingerprints готовых output artifacts — в schema v4 версии 0.7.39.

## Назначение

Report Passport — детерминированный JSON-sidecar, который описывает происхождение PDF,
изображения, CSV/XLSX, DOCX/HTML или другого отчётного результата. При неизменных данных,
ReportDefinition, языке, параметрах рендера и output bytes повторная генерация создаёт тот же
`passport_sha256`.

```text
report.pdf
report.pdf.passport.json
```

Физическая печать не создаёт файл, поэтому для неё доступен только предварительный digest без
output artifact и файлового sidecar.

## Покрытые сценарии

- Print Center: PDF и постраничные PNG/JPEG/TIFF/BMP/WebP/SVG;
- прямой PNG/SVG/PDF активной визуализации;
- CSV/XLSX выбранного интервала;
- Masterlog PDF;
- интерпретационный PDF;
- DOCX и HTML через общий отчётный контракт;
- физическая печать: digest без файлового sidecar.

## Что фиксируется

- версия приложения и schema паспорта;
- проект, скважина, dataset или well-level artifact;
- индекс, точный интервал, sample count и SHA-256 значений индекса;
- fingerprints фактических значений выбранных каналов;
- semantic bindings, UOM, sensor/source, confidence, aliases и evidence;
- coverage: availability, observed, zeros, missing и unavailable;
- формулы, версии и SHA-256 выражений;
- form/template/report-definition revision и SHA-256;
- язык RU/KK/EN;
- renderer, формат, DPI, media, orientation, margins, Fit/100% и continuations;
- source/import/lossless fingerprints;
- basename, role/page, MIME, byte size и SHA-256 готовых artifacts.

## Приоритет fingerprint источника

1. `LasSourceSnapshot` — `stored-at-import`.
2. Встроенный lossless LAS artifact — `embedded-project-artifact`.
3. Доступный внешний CSV/Excel/Paradox/LAS — `captured-at-report-time`.
4. Нормализованный snapshot фактических данных отчёта — всегда.

Абсолютные source/output paths в паспорт не входят.

## Проверка и файловая транзакция

Паспорт финализируется только после записи output во staging. Для каждого файла сохраняются
безопасное имя без каталогов, роль `single-file` или `page`, номер страницы, MIME, размер и
SHA-256 фактических bytes.

`load_report_passport()` проверяет digest JSON, наличие output, размер и SHA-256. Output и sidecar
устанавливаются recoverable transaction schema v1:

```text
staging → output fingerprint → signed passport → journaled backup/install
→ installed-file verification → committed → cleanup
```

Сбой до `committed` восстанавливает предыдущую пару. Сбой после `committed` сохраняет новую пару
и завершает cleanup. Подробнее: [REPORT_OUTPUT_TRANSACTION.md](REPORT_OUTPUT_TRANSACTION.md).

## Детерминизм

- JSON канонизируется с сортировкой ключей;
- timestamp, случайные ID и абсолютные output paths отсутствуют;
- `NaN`, Infinity и signed zero нормализуются в инженерных fingerprints;
- digest считается по payload без поля `passport_sha256`;
- fingerprints зависят от выбранного интервала и готовых output bytes.

## Сохранение и повторная проверка

Паспорт создаётся при успешном экспорте отчёта. Он не заменяет сохранение проекта через
**Ctrl+S**. Для проверки храните output и sidecar рядом, затем повторно откройте sidecar через
поддерживаемую команду проверки. Перемещение пары допустимо, так как абсолютные output paths в
паспорт не входят; переименование или изменение output нарушит проверку fingerprint.

## Ограничения

- механизм не является электронной подписью организации или trusted timestamp;
- physical print не имеет output-file fingerprint;
- recovery journal может содержать временные absolute paths, но они не входят в паспорт;
- Windows/NTFS/network-share/PDF/HiDPI/physical-print smoke-test обязателен перед stable.
