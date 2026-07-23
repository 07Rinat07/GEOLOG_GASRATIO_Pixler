# Жоба мәртебесі

Кесім: 2026 жылғы 23 шілде. Нұсқа: 0.7.37, тесттік жинақ.

## Орындалды

- ортақ coverage schema v1 нақты нөлді, missing sample және unavailable channel күйін ажыратады;
- `ReportDefinition` schema v2 тұрақты curve IDs және күтілетін мнемоникаларды сақтайды;
- `ResolvedReportDefinition` unavailable channels және interval coverage қайтарады;
- CSV ішінде сәйкесінше `0`, бос ұяшық және `#N/A` қолданылады;
- XLSX, JSON, Parquet, interval statistics, Curve Catalog және Report Passport бір coverage contract қолданады;
- Report Passport schema v2 нұсқасына көтерілді;
- project format v16 болып қалады.

Тексерулер: 57 мақсатты тест өтті, 1 optional Parquet scenario skipped; қолжетімді регрессия —
876 passed, 4 skipped, 3 LAS tests deselected. Толық Qt/LAS/Ruff/mypy gate және Windows print
smoke-test міндетті болып қалады.

Келесі кезең: A4/A3/custom/roll, 100%/fit, page continuation және physical printer gate.

[Coverage моделі](COVERAGE_MODEL.md), [ReportDefinition](REPORT_DEFINITION.md) және
[жалпы мәртебе](../PROJECT_STATUS.md).
