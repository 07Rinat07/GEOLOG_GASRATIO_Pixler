# План проекта

Актуально на 23 июля 2026 года. Старые изменения находятся в `CHANGELOG.md` и release notes;
этот файл содержит только будущую работу и критерии приёмки.

## P0 — вернуть надёжный релизный контур

- [x] восстановить контракт маршрутизации аннотаций, включая
  `TabletView._annotation_ancestor` либо его документированную замену;
- [x] устранить аварийное завершение Qt-процесса в полном pytest;
- [x] исправить 6 ошибок Ruff;
- [x] устранить ошибки mypy, начиная с enum/`str`, `None`, сигнатур Qt и
  несогласованных моделей геометрии;
- [x] выполнить полный набор: 1217 тестов пройдено, 10 пропущено, процесс завершён с кодом 0;
- [ ] провести Windows/HiDPI/PDF/physical print smoke-test.

Автоматический критерий выполнен 23 июля 2026 года для baseline 0.7.28: Ruff чист,
mypy — 0 ошибок в 262 файлах, полный pytest зелёный. Сборка остаётся тестовой до ручного
smoke-test и повторного полного gate для текущей версии.

## P0 — уменьшить архитектурный риск

- [x] первым вертикальным срезом выделить из `TabletView` annotation event router без
  изменения жестов, контекстного меню и области видимости аннотаций;
- [x] выделить navigation coordinator для pan/zoom/home/end/keyboard с headless-тестами;
- [x] вынести plan/order/reuse жизненного цикла треков; перестановка и Undo/Redo сохраняют
  существующие графики без полного rebuild;
- [x] вынести создание/регистрацию/удаление треков, включая rollback частичной сборки и
  очистку event filters, viewport maps и overlay layers;
- [x] вынести общий grid renderer экрана/печати и применять настройки крупных и
  промежуточных делений при частичном обновлении трека;
- [x] сделать edit-mode controller единственным владельцем состояния F4 и активного
  инструмента аннотаций, без дублирующих флагов в `TabletView`;
- [x] вынести доступность и переходы «Главная ↔ workspace ↔ целевая вкладка» из
  `MainWindow` в headless-controller;
- [x] вынести стабильные типы источников и маршрутизацию универсального импорта в
  headless `ImportJobController`;
- [x] вынести выполнение CSV/Excel планов, LAS policy jobs и регистрацию Paradox dataset в
  единый `DatasetImportJobExecutor` внутри `services`;
- [x] вынести print jobs, session binding и оставшиеся команды дерева workspace;
- [x] запретить UI-классам напрямую менять сериализуемую модель проекта;
- [x] покрыть новые print/session/workspace границы headless- и source-integrity тестами до
  переноса следующего сценария.

Критерий текущих срезов выполнен: маршрутизация аннотаций, навигация, инженерная сетка,
LAS/CSV/Excel/Paradox import jobs, выполнение печати, перепривязка project session, команды
дерева и изменяющие операции сериализуемой модели проверяются отдельно от `MainWindow`.
Qt-слой сохраняет диалоги, жесты, выбор пользователя и отображение результата; commit/rollback
проходят через controller/service boundary.

## P0 — единые данные и воспроизводимый отчёт

- [x] создать Semantic Channel Dictionary: canonical kind, quantity class, UOM, aliases,
  source/sensor и исходная мнемоника; сохранять binding каждой кривой в формате проекта v16;
- [x] добавить единый интерактивный Import Review для индекса, mapping, единиц, NULL и QC;
  preview и commit выполняются на копии, а отмена не изменяет проект;
- [ ] ввести Report Passport с fingerprint источника, bindings, версиями формул, UOM,
  revision формы, языком и настройками рендера;
- [ ] добавить golden fixtures для экранной и печатной сетки, легенд, литотипов и аннотаций.

Semantic Channel Dictionary и интерактивный Import Review выполнены: CSV/Excel, LAS и Paradox
используют один resolver, пользователь проверяет индекс, NULL, mapping и UOM до регистрации, а
отмена не изменяет проект. Следующий подэтап — Report Passport. Критерий всего блока: повторный
отчёт из неизменившегося проекта имеет тот же паспорт и проверяемый результат.

## P1 — операционная геология и real-time

- [ ] типизированные события drilling/gas/show/sample/casing/top;
- [ ] append-only growing dataset, checkpoint и детерминированный replay;
- [ ] QC для gap, duplicate, out-of-order, stale и calibration;
- [ ] версионированная lag/depth correction с просмотром исходной и скорректированной оси;
- [ ] offline WITSML 2.1 inventory и mapping;
- [ ] защищённый ETP 1.2 client после успешного replay, без credentials в JSON проекта.

Критерий: записанный поток воспроизводится повторно с теми же событиями, QC и отчётом.

## P1 — единая печать и отчётность

- [ ] одна `ReportDefinition` для геологии, шлама, кальциметрии, ЛБА, газа, бурения и событий;
- [ ] единый interval selection для preview, PDF и табличного экспорта;
- [ ] coverage и явное различение нуля, пропуска и отсутствующего канала;
- [ ] A4/A3/custom/roll, 100%/fit, page continuation и физический printer gate;
- [ ] экспорт PDF/XLSX/CSV/TSV; DOCX и HTML — после доказанного общего ядра.

## P2 — multiwell и автоматизация

- [ ] correlation canvas с tops, ties и независимыми шкалами;
- [ ] многоскважинные выборки и статистические/crossplot views;
- [ ] versioned plugin/API contracts;
- [ ] ограниченный Python console с журналом, timeout и явным разрешением изменяющих команд.

## Правила выполнения

- один вертикальный срез должен заканчиваться пользовательским сценарием, тестами и RU/KK/EN;
- исходные LAS/DB не перезаписываются скрытно;
- «готово» означает зелёные автоматические проверки и указанный ручной smoke-test;
- closed/proprietary formats не обещаются без спецификации, fixtures и loss matrix.

Основание приоритетов: [аудит продукта](PRODUCT_AUDIT_2026.md).
