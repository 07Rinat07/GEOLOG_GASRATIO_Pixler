# Report Passport

Статус: реализовано с версии 0.7.34. Coverage добавлен в schema v2, печатная модель — в schema v3,
а fingerprints готовых output artifacts — в schema v4 версии 0.7.39. Формат проекта остаётся v16.

## Назначение

Report Passport — детерминированный JSON-sidecar, который объясняет происхождение конкретного
PDF, изображения, CSV/XLSX или другого отчётного результата. Для неизменившихся данных, формы,
языка, параметров рендера и output bytes повторная генерация создаёт тот же `passport_sha256`.

```text
report.pdf
report.pdf.passport.json
```

Физическая печать не имеет файла, поэтому вычисляется предварительный digest без artifacts и
sidecar не создаётся.

## Покрытые сценарии

- Print Center: PDF и постраничные PNG/JPEG/TIFF/BMP/WebP/SVG;
- прямой PNG/SVG/PDF активной визуализации;
- CSV/XLSX выбранного интервала;
- Masterlog PDF;
- интерпретационный PDF;
- физическая печать: digest без файлового sidecar.

## Что фиксируется

- версия приложения и schema паспорта;
- проект, скважина, dataset либо well-level artifact;
- точный индекс и интервал, sample count и SHA-256 значений индекса;
- fingerprints фактических значений выбранных каналов;
- полный semantic binding, UOM, sensor/source, confidence, aliases и evidence;
- coverage: availability, observed, zeros, missing и unavailable;
- формулы, версии и SHA-256 выражений;
- form/template/report-definition revision и SHA-256;
- язык RU/KK/EN;
- renderer, формат, DPI, media, orientation, margins, Fit/100% и continuations;
- source/import/lossless fingerprints;
- artifacts готового результата: basename, role/page, MIME-type, byte size и SHA-256.

## Приоритет fingerprint источника

1. `LasSourceSnapshot` — `stored-at-import`.
2. Встроенный lossless LAS artifact — `embedded-project-artifact`.
3. Доступный внешний CSV/Excel/Paradox/LAS — `captured-at-report-time`.
4. Нормализованный snapshot фактических данных отчёта — всегда.

Абсолютные source/output paths в паспорт не входят.

## Schema v4: готовые output artifacts

Паспорт финализируется только после того, как renderer завершил запись в staging. Для каждого
файла сохраняются:

- безопасный `file_name` без каталогов;
- `single-file` либо `page`;
- номер страницы для paged export;
- MIME-type;
- размер;
- SHA-256 фактических bytes.

`load_report_passport()` проверяет JSON digest, наличие output, размер и SHA-256. Изменение уже
созданного PDF, изображения, CSV или XLSX обнаруживается.

## Filesystem transaction schema v1

Output и sidecar не устанавливаются независимыми операциями. Последовательность:

```text
staging → output fingerprint → signed passport → journaled backup/install
→ installed-file verification → committed → cleanup
```

Сбой до `committed` восстанавливает предыдущую пару. Сбой после `committed` сохраняет новую пару
и завершает только cleanup. Подробнее: [REPORT_OUTPUT_TRANSACTION.md](REPORT_OUTPUT_TRANSACTION.md).

## Детерминизм

- JSON канонизируется с сортировкой ключей;
- timestamp, случайные ID и абсолютные output paths отсутствуют;
- `NaN`, Infinity и signed zero нормализуются в инженерных fingerprints;
- digest считается по всему payload кроме `passport_sha256`;
- fingerprints зависят от фактического интервала и готовых output bytes.

## Ограничения

- это не электронная подпись организации и не trusted timestamp;
- физическая печать не имеет output artifact fingerprint;
- recovery journal содержит временные absolute paths, но они не входят в passport;
- Windows/NTFS/network-share/PDF/HiDPI/physical-print smoke-test обязателен перед stable.

## DOCX и HTML в 0.7.40

Passport schema v4 сохраняет безопасное имя, MIME, размер и SHA-256 готового DOCX/HTML. Любое
изменение документа после экспорта обнаруживается при загрузке sidecar.
