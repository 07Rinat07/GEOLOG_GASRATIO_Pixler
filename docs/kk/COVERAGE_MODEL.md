# Ортақ coverage моделі

0.7.37 нұсқасы деректердің төрт күйін ажыратады:

- `observed_value` — шекті және нөлге тең емес мән;
- `observed_zero` — нақты шекті нөл;
- `missing_sample` — арна бар, бірақ отсчёт `NaN/Infinity`;
- `channel_unavailable` — есеп сұраған арна dataset ішінде жоқ.

`ReportDefinition` schema v2 тұрақты curve IDs және күтілетін мнемоникаларды қабылдайды.
Resolver табылмаған мнемоникаларды unavailable ретінде сақтайды және coverage мәнін тек
resolved interval жолдары бойынша есептейді.

CSV ішінде нөл `0`, missing sample бос ұяшық, unavailable channel `#N/A` ретінде жазылады. XLSX
`Parameters` парағында availability, observed, zeros, missing және coverage көрсетіледі. JSON,
Parquet және Report Passport schema v2 құрылымдалған coverage payload сақтайды.

Project format v16 болып қалады. Толық contract: [COVERAGE_MODEL.md](../COVERAGE_MODEL.md).
