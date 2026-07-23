# Примечания к выпуску 0.7.38 — единая печать

- A4/A3/custom/roll используют одну физическую модель;
- добавлены Fit и 100% с нумерованными продолжениями;
- preview, PDF, файлы и принтер используют один `PrintDocumentPlan`;
- выбранный в системном диалоге page range учитывается в gate;
- printer gate проверяет устройство, media, размеры, поля, printable area и DPI;
- добавлен `tools/physical_print_gate.py` с явным `--print-test`;
- Report Passport использует schema v3; project format остаётся v16.

Подробнее: [Форматы и масштаб печати](PRINT_MEDIA_MODEL.md).
