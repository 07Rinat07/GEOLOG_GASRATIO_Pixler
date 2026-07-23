# Статус проекта

Срез: 23 июля 2026 года. Версия: 0.7.38, тестовая сборка.

## Выполнено

- одна print-media schema v1 для A4/A3/custom/roll;
- Fit и 100% при reference DPI 96;
- вертикальные страницы и горизонтальные продолжения образуют один детерминированный план;
- preview, PDF, постраничные файлы и физический принтер используют один job;
- системный page range учитывается в printer gate и итоговом счётчике;
- gate проверяет media, размеры, поля, printable area, DPI и состояние устройства;
- Report Passport повышен до schema v3;
- формат проекта остаётся v16.

Проверки: 56 целевых тестов и 27 print-specific tests пройдены; доступная регрессия —
910 passed, 4 skipped, 3 LAS tests deselected. Полный Qt/LAS/Ruff/mypy gate и аппаратный
Windows/HiDPI/PDF/physical-print smoke-test остаются обязательными.

Следующий этап: filesystem-транзакция output + passport и fingerprint готового файла.

См. [Форматы печати](PRINT_MEDIA_MODEL.md) и [общий статус](../PROJECT_STATUS.md).
