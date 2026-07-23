# Примечания к выпуску 0.7.39 — транзакция output и Report Passport

Тестовая архитектурная сборка. Формат проекта остаётся v16.

- добавлена recoverable filesystem transaction schema v1 для output + passport sidecar;
- renderer пишет в staging, затем готовые байты получают SHA-256 и размер;
- Report Passport повышен до schema v4 и содержит fingerprints всех output artifacts;
- установленная пара повторно проверяется перед фиксацией `committed`;
- сбой до commit восстанавливает прежние файлы, сбой после commit завершает только cleanup;
- перезапись удаляет лишние старые страницы продолжения транзакционно;
- добавлен `tools/recover_report_transactions.py`;
- Print Center, direct visualization, CSV/XLSX, Masterlog и interpretation PDF используют одну границу.

Проверено: 37 целевых тестов; доступная регрессия — 915 passed, 4 skipped, 3 LAS tests deselected.
Полный Qt/LAS/Ruff/mypy и Windows filesystem/PDF smoke-test остаются обязательными.
