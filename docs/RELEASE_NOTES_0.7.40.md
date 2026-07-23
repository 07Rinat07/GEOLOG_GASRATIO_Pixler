# Примечания к выпуску 0.7.40 — DOCX и HTML export adapters

Тестовая архитектурная сборка. Формат проекта остаётся v16, Report Passport — schema v4.

- добавлена общая Qt-независимая `ReportDocumentModel` schema v1;
- DOCX и self-contained HTML используют один `ResolvedReportDefinition` и точные row indices;
- Coverage одинаково различает реальный `0`, missing `—` и unavailable `#N/A`;
- DOCX формируется детерминированным OOXML без новой обязательной зависимости;
- HTML содержит inline CSS, не использует scripts и внешние ресурсы;
- оба адаптера записываются через recoverable filesystem transaction;
- Passport v4 фиксирует MIME, byte size и SHA-256 готового DOCX/HTML;
- в меню File добавлены локализованные действия RU/KK/EN.

Проверено: 73 passed целевых тестов; доступная регрессия — 926 passed, 4 skipped, 3 LAS-сценария deselected.
Полный Qt/LAS/Ruff/mypy и Windows Word/browser smoke-test остаются обязательными.
