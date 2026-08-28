<!-- runtime-contract: package=0.7.93; project=v22; form=v14; layout=v22 -->
# Единый план проекта

Актуально на 28 августа 2026 года. Это единственный канонический план проекта. Завершённые
изменения фиксируются в [CHANGELOG.md](CHANGELOG.md); отдельные roadmap, build report,
release plan и временные планы в `docs` не создаются.

## Правила ведения разработки

1. Перед материальным изменением проверяются этот план, архитектурные границы и существующие
   regression tests. Если меняется контракт, приоритет или риск — план обновляется в том же
   инкременте.
2. Тест исправляется только при осознанном изменении продукта. Нельзя ослаблять assertion,
   пропускать сценарий или изолировать файл только ради зелёного CI без установленной причины.
3. Задача считается завершённой только вместе с кодом, regression tests, нужной документацией
   RU/KK/EN, записью в `CHANGELOG.md` и успешными применимыми gates.
4. Исходные LAS/GS2/WITS/WITSML данные неизменяемы. Очистка, нормализация и расчёты выполняются
   над рабочими копиями с версионированным provenance.
5. Новые hot paths получают оценку сложности, bounded memory и benchmark. Новый внешний ввод
   получает лимиты, валидацию, безопасные ошибки и security tests.
6. После интеграции не должны оставаться временные ветки, trigger-файлы, диагностические workflow,
   сгенерированные artifacts или локальные пользовательские данные.
7. `main` остаётся пригодным для запуска. Большой рефакторинг делится на обратимо проверяемые
   инкременты; совместимость сериализуемых форматов не меняется без миграции.

## Текущая база

- пакет `0.7.93`; project `v22`; form `v14`; tablet layout `v22`;
- desktop-модульный монолит: Python 3.11, PySide6, PyQtGraph, NumPy;
- WITS0, WITSML 1.4.1.1, WITSML 2.x/ETP foundation, GS2/Paradox, LAS, планшет, формы,
  расчёты и отчёты реализованы;
- комплексная газовая A4-форма использует один видимый общий depth track и семь графических
  секций без удаления внутренних синхронных depth tracks; порядок секций соответствует
  integrated gas log: ROP, C1–C5, Total Gas, normalized/relative gas, diagnostic ratios и Pixler;
- печатная шапка выводит все семь C1–nC5 rows; повторная конечная шапка занимает отдельную
  финальную страницу и использует ширину графика, не уменьшая последнюю страницу планшета;
  off-scale samples клипуются через bounded overscan без искусственных `NaN`-фрагментов и
  небезопасных painter coordinates;
- C1–C5 теперь проходят Qt-независимое bounded conditioning до расчёта `TG_CALC`, относительных
  компонентов, Haworth и Pixler; исходные кривые не перезаписываются;
- Windows quality, GUI/HiDPI/PDF и security gates автоматизированы; реальная физическая печать,
  полевые interoperability и длительные soak gates остаются ручными/полевыми критериями;
- preview и physical printer больше не создают скрытые PDF; legacy timestamp-копии и аварийные
  временные файлы очищаются только по строгому application-owned контракту;
- колонка системного типа `INTERPRETATION` может иметь пользовательское отображаемое название;
  сохранённое описание породы из `CuttingsSample.description` видно в ней на планшете и в печати.
  `Shift + левая кнопка` создаёт интервал описания с точной коррекцией границ, шаблоном
  RU/KZ/EN или произвольным rich text без обязательного заполнения процентов;
- заводские MASTERLOG A4 portrait/landscape используют локализованное отображаемое название
  «Описание пород» для системной колонки `INTERPRETATION`; книжная форма содержит эту колонку и
  укладывается в A4 при безопасных минимальных ширинах без скрытого print scaling;
- универсальный импорт принимает файл одним действием и определяет LAS/CSV/TXT/Excel/Paradox/GS2
  по расширению; обычный LAS использует совместимую политику, а расширенные политики и вторичные
  настройки Import Review остаются доступны через отдельную команду и раскрываемые разделы;
- пользовательские project/LAS sidecars исключены из новых коммитов; опубликованная история Git
  требует отдельного согласованного решения SEC-01.

## Принятые инженерные ориентиры

- **CWLS LAS 2.0** — обменный формат цифровых каротажных кривых, а не контейнер всего
  редактируемого проекта.
- **SLB Techlog и Aspen Geolog** — ориентир для последовательности `load/QC → common sampling →
  calculations → interpretation → presentation`, версионированных workflows и отделения
  исходных измерений от производных результатов. Закрытый vendor-код не копируется.
- **WellCAD и LogPlot** — ориентир для разделения рабочего документа, layout и обменного LAS,
  безопасного merge и резервных копий.
- **Leapfrog Energy** — ориентир для autosave, Save a Copy и переносимого backup.
- **Energistics ETP/WITSML** — version/provenance envelope и реальная interoperability matrix.
- **PyQtGraph, NumPy, lasio и другие open-source компоненты** используются только после проверки
  лицензии, актуального API, производительности и соответствия нашим доменным контрактам.
- **OWASP File Upload/XXE guidance** — defense in depth, bounded resources, запрет внешних XML
  сущностей и недоверенных путей.

## P0 — выпуск и безопасность

- [x] **REL-02:** hash-pinned Windows/Python 3.11 runtime, CycloneDX SBOM,
  dependency/secret/static scans и отдельные quality/security artifacts.
- [ ] **REL-03:** завершить Windows GUI/HiDPI/PDF/physical-printer matrix с реальным отпечатком,
  цветом, clipping, полями драйвера и операторским checklist.
- [ ] **SEC-01:** согласовать очистку опубликованной Git history от пользовательских project/LAS
  sidecars и проверить clones, caches, forks и releases.
- [x] **SEC-02:** bounded ETP multipart по размеру, числу частей и времени сборки.
- [x] **SEC-03:** bounded streaming LAS/XML; DTD/entity/external entity/notation блокируются до
  materialization.
- [x] **SEC-04:** WITS0 retention ограничен application-owned каталогом; remote bind использует
  явное подтверждение и CIDR allowlist.
- [ ] **SEC-05:** завершить provenance/license review встроенных lithology/symbol assets.

## P0 — целостность газовых данных и расчётов

- [x] **GAS-01:** введён Qt-независимый `gas_conditioning` с immutable input, строгой проверкой
  оси, поддержкой возрастающей/убывающей глубины и повторяющихся depth rows.
- [x] **GAS-02:** интерполируются только короткие bounded `NaN`-интервалы; длинные остановки,
  ведущие/хвостовые пропуски и реальные нули сохраняются. Для каждой кривой возвращается маска
  интерполированных строк и фактический max-gap.
- [x] **GAS-03:** `ProjectSession.calculate_basic_gas_ratios()` сначала кондиционирует C1–C5,
  затем рассчитывает `TG_CALC`, `*_REL`, Haworth, изомеры и Pixler. Исходные LAS-кривые не
  изменяются; производные кривые имеют provenance `conditioned-gas-ratio:2.0`.
- [x] **GAS-04:** экранная геометрия применяет gas-only short-gap policy, сохраняет контекстные
  точки на границах viewport/страниц и не распространяет интерполяцию на GR/ROP/DEXP.
- [x] **GAS-05:** calculation conditioning и render sampling используют единый Qt-независимый `CurveContinuityPolicy`; gas-only viewport geometry кондиционируется до обрезки, а экран/PDF/preview/printer получают явный segment mask.
- [x] **GAS-09:** встроенная комплексная форма использует отраслевой порядок ROP/C1–C5/Total
  Gas/normalized/relative/ratios/Pixler, а полный семикомпонентный заголовок и bounded off-scale
  clipping одинаково работают на экране, preview, PDF и последней странице.
- [x] **GAS-10:** GeoScape2 `Sensors.DB` сверён по всем 317 GID; resolver поддерживает
  международные/нестандартные изомерные и bit-size aliases, сворачивает только эквивалентные
  дубли и по семикомпонентному контракту GeoScape трактует старые `C4/C5` рядом с
  `iC4/iC5` как прямые контекстные алиасы `nC4/nC5` без изменения измерений; канонический
  набор и структура mud log сверены с официальными материалами SLB.
- [ ] **GAS-06:** сохранять структурированный QC provenance conditioning в проекте и показывать
  оператору количество/диапазоны восстановленных точек без изменения исходного LAS.
- [ ] **GAS-07:** добавить обезличенный golden dataset для интервала `1703.28–1753.28 м` и
  реальных sparse C1–C5: сравнивать source, conditioned, derived, screen segments и PDF pages.
- [ ] **GAS-08:** закрепить benchmark conditioning/ratios на 100k и 1M строк: линейное
  масштабирование, ограниченный peak RSS и отсутствие покадрового пересчёта при scroll/zoom.

## P0 — рабочий проект и сохранность данных

- [ ] **PROJ-01:** унифицировать терминологию «источник → проект → экспорт», показывать путь
  проекта после первого импорта и вынести **«Сохранить LAS»** в общий export controller.
- [ ] **PROJ-02:** dirty close guard, autosave после материальных операций и ротационные backup
  с проверяемым восстановлением после сбоя.
- [ ] **PROJ-03:** переносимый архив проекта с JSON, `.assets`, manifest, SHA-256 и проверкой до
  открытия.
- [ ] **PROJ-04:** неизменяемый реестр каждого суточного LAS/GS2 с raw artifact, fingerprint,
  диапазоном, import report и транзакционным откатом отдельного добавления.

## P0 — производительность и хранение

- [x] **PERF-01:** acquisition `append_many()` batch 64, геометрические buffers, logical rollback
  и incremental hash chains.
- [ ] **PERF-02:** checkpoint/replay без двойного хранения materialized Dataset и journal.
- [ ] **PERF-03:** обязательный benchmark 50k/100k/1M: `T(2N)/T(N) <= 2.5`, p95 batch64
  `<= 50 ms`, last/first 10k `<= 2`.
- [ ] **PERF-04:** revision-based tablet caches с byte budget; cold/hit/zoom и peak RSS на
  1/5/10 млн samples.
- [ ] **PERF-05:** совместимый versioned storage port: manifest, column chunks, atomic commit и
  crash recovery вместо монолитного JSON для больших проектов.
- [x] **PERF-06:** исключён двойной PDF-render для preview/printer; постоянный файл создаётся
  только явным export job, временные файлы имеют ownership-prefix и bounded stale cleanup, а
  миграционная очистка legacy-копий fails closed при постороннем содержимом каталога.

## P1 — поддерживаемая архитектура

- [x] **IMPORT-UX-01:** основной импорт сокращён до маршрута «выбрать файл → компактно проверить
  → подтвердить». Формат определяется по расширению; совместимый LAS является безопасным
  стандартным путём. Строгий/ручной режимы, индекс/NULL, ручное сопоставление, технические
  метрики и подробные предупреждения сохранены как явно раскрываемые дополнительные настройки.

- [x] **CUT-01:** единый экранный и печатный контракт описания шлама: `CuttingsSample.description`
  отображается в `INTERPRETATION`, rich HTML безопасно преобразуется для печати, а сохранённое
  отображаемое название колонки не заменяется системным. Старые интервалы интерпретации
  сохраняются и остаются видимыми вне перекрывающего описания.
- [x] **CUT-02:** в режиме выбора `Shift + левая кнопка` на дорожках описания и интерпретации
  создаёт интервал свободного описания; диалог позволяет точно исправить кровлю/подошву,
  выбрать готовый шаблон RU/KZ/EN или ввести любой форматированный текст. Двойной щелчок
  повторно открывает описание; удаление текста не удаляет состав, ЛБА или кальциметрию пробы.
- [x] **CUT-04:** экран и Masterlog/PDF автоматически переносят слова и уменьшают шрифт описания
  до безопасного минимума. Если полный текст физически не помещается, экран показывает
  сокращение с многоточием и восстанавливает полный текст после увеличения масштаба; печатный
  painter жёстко ограничен прямоугольником интервала. Выравнивание слева, по центру или справа
  выбирается в rich-text редакторе, сохраняется в HTML и применяется на экране и в печати.
  Адаптация пересчитывается по фактической ширине viewport после каждого изменения ширины колонки;
  перенос слов можно отключить отдельным сохраняемым флажком, включённым по умолчанию.
- [x] **CUT-05:** в обе заводские формы MASTERLOG A4 включена системная колонка
  `INTERPRETATION` с названием «Описание пород»; книжные ширины перераспределены до `714/718 px`,
  а regression-тест фиксирует состав, локализацию RU/KK/EN и отсутствие скрытого масштабирования.
- [ ] **CUT-03:** включить длинные rich-text описания и встроенные фотографии шлама в ручную
  матрицу реальной печати A4/A3 в составе **REL-03**: проверить перенос, границы интервала,
  пользовательский заголовок и читаемость на физическом отпечатке.

- [x] **RULER-01:** единый Qt-независимый контракт глубинных/временных отметок, общей частоты и индивидуальной видимости колонок сериализуется в tablet layout v22; layouts v1–v21 получают безопасную миграцию.
- [x] **RULER-02:** настройки видимости и частоты внутренней шкалы подключены к редактору живой графической колонки и редактору структуры формы на RU/KK/EN; сохраняются в layout v22 и form schema v14, а формы v1–v13 получают безопасный automatic/visible default.
- [x] **RULER-03:** screen, preview, PDF и printer используют один resolved ruler; печатный snapshot сохраняет общий layout и фактические ticks колонок, а regression tests проверяют общий page-boundary и восстановление экранного состояния.
- [x] **RULER-04:** после стабилизации шкал внедрён единый gas continuity/segment mask для C1–C5, relative gas, Haworth и Pixler с сохранением длинных остановок и реальных нулей.

- [ ] **ARCH-01:** `ApplicationContext`/composition root для storage, semantic, import, report,
  credentials и audit services.
- [ ] **ARCH-02:** разделить `MainWindow` на feature coordinators; запретить UI прямые записи в
  project collections, Dataset, layout и dirty-state.
- [ ] **ARCH-03:** вынести оставшиеся sampling/cache/navigation/track lifecycle/editing state из
  `TabletView` в Qt-независимые компоненты с transition tests.
- [ ] **ARCH-04:** один immutable `SemanticContext` для всех importers с source mnemonic, UOM,
  mapping evidence и версией каталога.
- [ ] **ARCH-05:** закрепить границы слоёв AST/import-contract тестами и запретить зависимости
  domain/calculations от Qt/UI/printing.
- [ ] **ARCH-06:** calculation profiles и conditioning policies сделать версионированными
  immutable DTO; UI выбирает профиль, но не реализует формулы или interpolation.

## P1 — полевая совместимость

- [ ] **FIELD-01:** обезличенный WITS0 поток; reconnect/restart/disk-full и 8–24-часовой Windows soak.
- [ ] **FIELD-02:** WITSML 1.4.1.1 минимум на двух Store implementations.
- [ ] **FIELD-03:** ETP 1.2 matrix: TLS/auth/proxy, paging, quality, reconnect, replay и
  subscription recovery.
- [ ] **FIELD-04:** GS2/Paradox минимум на трёх обезличенных версиях; сравнить TIME/DEPTH,
  C1–C5, total gas, UOM, Gas Ratio и Pixler с эталонным export.
- [ ] **FIELD-05:** standard/version/provenance envelope для WITSML 2.1/ETP 1.2, PWLS property
  kinds и Energistics UOM.

## P2 — расширение после P0/P1

- [ ] **EXT-01:** versioned read-only API на immutable DTO/snapshots.
- [ ] **EXT-02:** изменения только через validated transactional commands с permissions,
  timeout, audit и rollback; код при открытии проекта не выполняется.
- [ ] **EXT-03:** multiwell correlation и общий PDF только после performance/RSS gate.
- [ ] **EXT-04:** 3D и AI import требуют отдельных validation/provenance gates внутри этого
  плана и не входят в ближайший выпуск.

## Обязательная матрица для каждого инкремента

- **Domain/unit:** формулы, границы, NaN/zero/inf, ascending/descending/duplicate axes.
- **Application/integration:** controller/session transaction, dirty/provenance, повторный запуск,
  rollback и неизменность source.
- **UI/render:** screen, HiDPI, scroll/zoom, forms, lifecycle и отсутствие native Qt crash.
- **Output:** preview/PDF/printer используют один resolved range и одинаковую геометрию данных.
- **Compatibility:** project/form/layout migration и старые LAS/GS2 fixtures.
- **Performance:** большие массивы, cache hit/miss, bounded memory и отсутствие O(N²).
- **Security:** недоверенный ввод, пути, XML/archive limits, secrets и dependency audit.
- **Documentation:** runtime marker, архитектура, тестовые команды, RU/KK/EN и внутренние ссылки.

## Критерий завершения задачи

Задача закрывается только когда:

1. контракт и риски определены до изменения кода;
2. код находится в правильном слое и не создаёт скрытую вторую реализацию правила;
3. source data остаются неизменными либо изменение выполняется явной транзакционной командой;
4. добавлены positive, boundary, negative и regression tests;
5. Ruff, mypy, полный pytest, Windows acceptance и security gate проходят там, где применимо;
6. обновлены этот план при изменении приоритетов, `ARCHITECTURE.md`, `TESTING.md`, нужные
   инструкции RU/KK/EN и `CHANGELOG.md`;
7. рабочее дерево чистое, временные ветки/workflow/trigger/artifacts отсутствуют.
