# План проекта

Актуально на 24 июля 2026 года. Hotfix 0.7.48 делает шапку кривой полноценной
инженерной шкалой, показывает и сохраняет пользовательскую единицу и синхронизирует
деления с сеткой колонки. Project format остаётся v20, tablet layout повышен до v16.
Следующий предметный срез после Windows-подтверждения — offline WITSML 2.1 inventory.

## P0 — hotfix 0.7.48: инженерная шкала в шапке

- [x] показывать minimum/maximum контрастными редактируемыми полями по краям шкалы;
- [x] рисовать полную линию шкалы по ширине колонки с major/minor ticks;
- [x] использовать те же divisions, что и вертикальная сетка конкретной колонки;
- [x] вычислять промежуточные подписи для linear и logarithmic scale;
- [x] позволять подготовить оба предела до commit через `✓` или Enter;
- [x] редактировать display unit и linear/logarithmic mode прямо в шапке;
- [x] не пересчитывать значения при изменении display unit;
- [x] сохранять unit/range/scale/colors в layout и пользовательской форме;
- [x] мигрировать tablet layout v15 → v16 через `unit_override = null`;
- [ ] выполнить Windows/PySide6/HiDPI smoke-test широких и узких колонок.

Критерий 0.7.48: пользователь видит единицу и инженерную шкалу без открытия отдельного
диалога; деления совпадают с сеткой; настройки переживают сохранение и повторное открытие формы.

## P0 — hotfix 0.7.47: DB и диапазоны в шапке

- [x] считать mixed order глубины исправимым через сортировку только принятой копии;
- [x] переставлять все индексы и кривые одной стабильной перестановкой;
- [x] не менять исходный DB и loader-owned dataset;
- [x] показывать информационную причину `index-sorted-copy` и сохранять диагностику;
- [x] выбирать явный DEPT/DEPTH/MD в batch DB → LAS даже при mixed classification;
- [x] не угадывать между слабыми или равными generic-кандидатами;
- [x] применять профиль и сортировку экспортной копии перед LAS round-trip;
- [x] редактировать min/max прямо в шапке обычной кривой;
- [x] сохранять manual/auto range, имя, цвет текста и нижней линии в рабочей форме;
- [ ] выполнить Windows smoke-test `D1174.db`, `BLData.db`, batch DB → LAS и узких колонок.

Критерий 0.7.47: исправимый mixed order не блокирует импорт; строки всех каналов остаются
согласованными; неоднозначный индекс не выбирается молча; диапазон из шапки переживает
сохранение/повторное открытие формы.

## P0 — надёжный импорт и диагностика

- [x] заменить нетипизированный mouse-button mask сетки на `Qt.MouseButton.NoButton`;
- [x] не блокировать доступ к dataset из-за presentation-only ошибки сетки или планшета;
- [x] открывать табличный recovery workspace после успешной регистрации и неудачного рендера;
- [x] считать Import Review warnings неблокирующими и собирать их в общий отчёт;
- [x] перехватывать неожиданные ошибки отдельно для каждого файла и фиксировать точный этап;
- [x] сохранять severity, code, source, action, context, exception type и traceback;
- [x] автоматически сохранять blocking report и поддерживать Copy/Save в интерфейсе;
- [x] читать duplicate LAS mnemonics по физическому столбцу и изолировать повреждённый канал;
- [ ] подтвердить реальный проблемный LAS и первый кадр на Windows/PySide6.

Критерий 0.7.46: предупреждение не запрещает импорт; ошибка presentation не удаляет и не
скрывает зарегистрированный dataset; диагностический отчёт достаточен для воспроизведения и
содержит рекомендуемое действие.

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
  source/sensor и исходная мнемоника; binding введён в v16 и сохраняется в текущем v20;
- [x] добавить единый интерактивный Import Review для индекса, mapping, единиц, NULL и QC;
  preview и commit выполняются на копии, а отмена не изменяет проект;
- [x] ввести Report Passport с fingerprint источника, bindings, версиями формул, UOM,
  revision формы, языком и настройками рендера;
- [x] добавить golden fixtures для экранной и печатной сетки, легенд, литотипов и аннотаций.

Semantic Channel Dictionary, интерактивный Import Review и Report Passport выполнены. Паспорт
фиксирует только фактический интервал и каналы отчёта, исходные fingerprints, полный semantic
binding/UOM, версии формул, content-addressed revision формы, язык и параметры renderer. Print
Center, прямой PNG/SVG/PDF-экспорт, Masterlog PDF и интерпретационный PDF создают проверяемый
JSON-sidecar; физическая печать вычисляет тот же digest без файлового sidecar. Golden fixture
schema v1 фиксирует общую grid/legend/lithotype/annotation geometry в подписанных JSON и
составных SVG. `ReportDefinition` schema v2 теперь один раз фиксирует dataset/index, sections, stable curve IDs,
ожидаемые channel mnemonics, form revision, language и full/current/custom/selection interval; Print Center, Masterlog
и CSV/XLSX используют один resolved range, который также сохраняется в Report Passport.
Coverage schema v1 различает observed value, observed zero, missing sample и unavailable channel;
Report Passport schema v4 подписывает coverage, scale mode, continuation settings и fingerprints готовых output artifacts. Единая
print-media schema v1 разрешает A4/A3/custom/roll, Fit/100%, двумерный page plan и capability gate
после выбора физического устройства.

## P0 — ежедневная рабочая форма и наращивание LAS

- [x] показывать сетку графических колонок независимо от скрытых осей renderer;
- [x] настраивать сетку X/Y, основные/промежуточные деления, прозрачность и печать отдельно для каждой колонки;
- [x] показывать min/max шкалы в шапке и открывать ручную настройку из самой шапки;
- [x] сохранять цвет кривой, цвет названия и цвет линии под названием;
- [x] сохранять форму целиком: порядок/ширины колонок, кривые, шкалы, сетки, подписи, viewport, revision и annotation scope;
- [x] поставлять фоновый газ, пластовый газ и остальные заводские обозначения без фона и лишних полей;
- [x] поддержать много независимых DEPTH и TIME datasets в одной скважине;
- [x] добавлять суточный LAS только в явно выбранный dataset и запрещать TIME↔DEPTH перезапись;
- [x] пропускать идентичное перекрытие, блокировать конфликтующее и распознавать повторный файл по SHA-256;
- [x] хранить отдельный audit append history каждого dataset в project format v20;
- [x] установить 0,2 м как редактируемый шаг по умолчанию при создании глубинного LAS;
- [ ] добавить необязательный multi-dataset overlay в одной форме после отдельного alignment contract;
- [ ] добавить watcher каталога для полуавтоматического обнаружения новых суточных LAS после ручного подтверждения preview.

Критерий 0.7.45: ни одна операция импорта одного dataset не меняет другие DEPTH/TIME datasets,
их формы, значки, комментарии или настройки; конфликт не оставляет частично добавленных строк.

## P1 — операционная геология и real-time

- [x] типизированные события drilling/gas/show/sample/casing/formation-top с project format v17,
  revisioned controller и точной ReportDefinition projection;
- [x] QC для gap, duplicate, out-of-order, stale и calibration;
- [x] append-only growing dataset, checkpoint и детерминированный replay;
- [x] версионированная lag/depth correction с immutable revisions, preview и выбором исходной/скорректированной оси;
- [ ] offline WITSML 2.1 inventory и mapping;
- [ ] защищённый ETP 1.2 client после успешного replay, без credentials в JSON проекта.

Acquisition source/replay contract выполнен в 0.7.42. Versioned lag/depth correction завершена
в 0.7.44: source journal не изменяется, каждая revision создаёт отдельный derived dataset, а UI и
ReportDefinition явно выбирают source/corrected axis. Следующий критерий — read-only offline
WITSML 2.1 inventory и mapping fixtures до любого сетевого ETP-клиента.

## P1 — единая печать и отчётность

- [x] одна `ReportDefinition` для геологии, шлама, кальциметрии, ЛБА, газа, бурения и событий;
- [x] единый interval selection для preview, PDF и табличного экспорта;
- [x] coverage и явное различение нуля, пропуска и отсутствующего канала;
- [x] A4/A3/custom/roll, 100%/fit, page continuation и физический printer gate;
- [x] объединить запись output и passport sidecar в одну восстанавливаемую filesystem-транзакцию
  и добавить fingerprint готового output-файла;
- [x] экспорт PDF/XLSX/CSV/TSV через общий ReportDefinition/Coverage contract;
- [x] DOCX и HTML через общий ReportDefinition/Coverage contract, recoverable transaction и Passport v4.

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
