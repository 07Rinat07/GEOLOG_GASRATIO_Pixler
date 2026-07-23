
## Реализованный паспорт текущих экспортов

Начиная с 0.7.34 Print Center, прямой PNG/SVG/PDF, Masterlog PDF и интерпретационный PDF
создают детерминированный JSON-sidecar. Он фиксирует exact interval/channel values, source
fingerprints, semantic bindings/UOM, formula versions, form revision, language и render settings.
Это действующий provenance-слой; будущая общая `ReportDefinition` должна использовать тот же
контракт, а не создавать второй несовместимый паспорт. Подробнее: [REPORT_PASSPORT.md](REPORT_PASSPORT.md).
