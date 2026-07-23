# Примечания к выпуску 0.7.36 — единая ReportDefinition

- добавлена immutable `ReportDefinition` schema v1;
- full/current/custom/selection разрешаются один раз против точного dataset/index;
- Print Center preview и итоговый PDF/печать используют одинаковый диапазон;
- добавлен режим выбранного интервала;
- Masterlog preview/PDF/system preview и CSV/XLSX используют resolved definition;
- Report Passport сохраняет payload и SHA-256 определения;
- формат проекта остаётся v16.
- Проверки: 50 целевых и 865 доступных regression tests passed; 4 skipped, 3 LAS deselected.


Подробности: [Единая ReportDefinition](REPORT_DEFINITION.md).
