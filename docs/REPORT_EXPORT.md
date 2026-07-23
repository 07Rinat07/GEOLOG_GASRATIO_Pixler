
## Реализованный паспорт текущих экспортов

Начиная с 0.7.34 Print Center, прямой PNG/SVG/PDF, Masterlog PDF и интерпретационный PDF
создают детерминированный JSON-sidecar. Он фиксирует exact interval/channel values, source
fingerprints, semantic bindings/UOM, formula versions, form revision, language и render settings.
Это действующий provenance-слой. Начиная с 0.7.36 общая `ReportDefinition` использует этот же
контракт: sidecar содержит canonical definition payload и его SHA-256 вместе с фактически
разрешённым интервалом. Подробнее: [REPORT_DEFINITION.md](REPORT_DEFINITION.md) и
[REPORT_PASSPORT.md](REPORT_PASSPORT.md).

## Coverage в 0.7.37

`ResolvedReportDefinition` содержит coverage для каждого запрошенного канала. CSV сохраняет
реальный ноль как `0`, missing sample как пустую ячейку, а unavailable channel как `#N/A`. XLSX
дополнительно публикует availability/observed/zeros/missing/coverage на листе `Parameters`.
JSON, Parquet и Report Passport schema v3 используют тот же headless-контракт. Подробнее:
[COVERAGE_MODEL.md](COVERAGE_MODEL.md).

## Печатная модель 0.7.38

Print Center использует один media/scale contract для A4/A3/custom/roll. Fit создаёт одну горизонтальную страницу; 100% сохраняет ширину формы при reference DPI 96 и создаёт нумерованные продолжения. PDF и физический принтер являются одним многостраничным документом, raster/SVG — нумерованными файлами. Report Passport schema v3 подписывает scale mode и overlap. Подробнее: [PRINT_MEDIA_MODEL.md](PRINT_MEDIA_MODEL.md).
