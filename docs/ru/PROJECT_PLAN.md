# План проекта

Актуально на 27 июля 2026 года после среза 0.7.75. Здесь перечислена только незавершённая работа; реализованные
срезы находятся в [состоянии проекта](PROJECT_STATUS.md), корневой
[истории изменений](../CHANGELOG.md) и release notes.


## Приоритет: WITS0 append-only AcquisitionSession и live acquisition

Raw capture, типизированный parser и Import Review с immutable `AcquisitionDatasetSchema` готовы.
Незавершённая работа:

- [ ] получить 5–10 минут реального GSWITS raw-потока;
- [ ] подтвердить TCP mode, IP, порт, кодировку, header fields и интервалы records;
- [ ] сверить встроенный GeoScape profile и сохранённый custom profile с реальными record/item;
- [ ] преобразовать подтверждённые WITS0 frames в normalized measurement batches;
- [ ] создать append-only `AcquisitionSession` через `AcquisitionController`;
- [ ] добавить checkpoint, bounded queue, backpressure и controlled close;
- [ ] подключить current values и live time/depth graphs;
- [ ] выполнить Windows reconnect/soak/restart проверку.
## Приёмка GeoScape II GS2

- [ ] добавить версионные проекции и обезличенные Access/Paradox fixtures других версий GeoScape;
- [ ] проверить повреждённые, обрезанные и многочастные таблицы на воспроизводимых golden fixtures;
- [ ] сверить СГ-8 и минимум два других GS2 с эталонным экспортом GeoScape в LAS/Excel;
- [ ] подтвердить C1–C5, суммарный газ, TIME/DEPTH, единицы, диапазоны и разбиение файлов;
- [ ] проверить Gas Ratio/Pixler на каналах, доказанно сопоставленных через `GS2.mdb`.

Автоматический CSV/XLSX-тест числового TIME подтверждает общий resolved-export, но не заменяет
сверку с реальным эталонным LAS/Excel.

## Ручная приёмка 0.7.72

- [ ] проверить верхние командные строки на Windows при 100%, 125% и 150% DPI;
- [ ] перенести окно между ноутбуком и внешним монитором, включая F4 и повторные нажатия команд;
- [ ] проверить прозрачные и исходные значки со всеми восемью маркерами, **Shift** и поворотом;
- [ ] подтвердить повторный выбор, перемещение и resize сверхтонкого значка после **Ctrl+S** и
  повторного открытия;
- [ ] сравнить экран, preview, PDF и физическую печать для геометрии `0,01` логического пикселя.

## Release recovery

- [ ] устранить текущие ошибки и internal error mypy;
- [ ] выполнить подписанный tablet/annotation/PDF/HiDPI/physical-printer smoke checklist;
- [ ] публиковать stable build только после зелёного обязательного gate.

## Критерий приёмки

Окно не выходит за рабочую область монитора, правая команда редактирования остаётся доступной,
а сверхтонкий значок остаётся видимым, выбираемым и редактируемым без изменения сохранённой
геометрии. CSV/XLSX используют точные строки активной числовой DEPTH/TIME-оси.
