# План проекта

Актуально на 24 июля 2026 года. Версия **0.7.60** сохраняет project format v20, form schema v6 и tablet layout v16.

## P0 — 0.7.60: экранно-безопасная статистика интервала и дисциплина README

- [x] заменить floating `QDockWidget` дочерним overlay внутри планшета;
- [x] исключить влияние панели на ширину формы;
- [x] ограничить размер и положение границами рабочей области;
- [x] сохранять ручное положение при resize без возврата вправо;
- [x] очищать selection, shading и отчёт при закрытии, смене формы и dataset;
- [x] уплотнить кнопки панели для узкой ширины;
- [x] добавить pure geometry, source-contract и Qt regression-тесты;
- [x] очистить корневой README от release notes и технических результатов;
- [x] добавить автоматический README scope-test;
- [ ] Windows/PySide6: проверить drag/resize/close/form-switch при DPI 100%, 125% и 150%.

Критерий выхода: панель остаётся внутри планшета, не сжимает форму, не возвращается вправо после ручного перемещения и полностью очищается при смене формы.

## Следующие этапы

- [ ] read-only offline WITSML 2.1 inventory и mapping fixtures;
- [ ] alignment-controlled multi-dataset overlays в одной форме;
- [ ] directory watcher с preview-подтверждением ежедневного прироста;
- [ ] secured ETP 1.2 только после успешного fixture replay.
