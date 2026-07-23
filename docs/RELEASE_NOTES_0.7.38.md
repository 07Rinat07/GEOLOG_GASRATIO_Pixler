# Примечания к выпуску 0.7.38 — единая модель печати

## Основное

- добавлен Qt-независимый `printing/print_layout.py` для A4/A3/custom/roll;
- введены режимы `Fit` и физический `100%` при reference DPI 96;
- горизонтальные продолжения строятся детерминированно с overlap в миллиметрах;
- `PrintDocumentPlan` объединяет вертикальные интервалы и горизонтальные продолжения;
- preview, PDF, постраничные raster/SVG и физический принтер используют один job;
- прямой PDF активной визуализации поддерживает продолжения; однофайловый raster/SVG явно
  отклоняет многостраничный 100% и направляет пользователя в Print Center;
- системный диалог получает полный диапазон `1…N`, а выбранный page range учитывается в gate;
- добавлен physical printer capability gate для media, bounds, margins, printable area, DPI и state;
- добавлен безопасный Windows-инструмент `tools/physical_print_gate.py`;
- Report Passport повышен до schema v3 и подписывает scale/continuation settings;
- формат проекта остаётся v16.

## Проверки

Фактические цифры автоматического gate фиксируются в `PROJECT_STATUS.md` и `TESTING.md`.
Аппаратный Windows/HiDPI/PDF/physical-print smoke-test остаётся обязательным перед stable.
