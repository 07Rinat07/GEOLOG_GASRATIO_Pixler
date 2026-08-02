<!-- runtime-contract: package=0.7.93; project=v22; form=v13; layout=v22 -->
# Единый план проекта

Актуально на 2 августа 2026 года. Это единственный канонический план проекта. Завершённые
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

- пакет `0.7.93`; project `v22`; form `v13`; tablet layout `v22`;
- desktop-модульный монолит: Python 3.11, PySide6, PyQtGraph, NumPy;
- WITS0, WITSML 1.4.1.1, WITSML 2.x/ETP foundation, GS2/Paradox, LAS, планшет, формы,
  расчёты и отчёты реализованы;
- комплексная газовая A4-форма использует один видимый общий depth track и семь графических
  секций без удаления внутренних синхронных depth tracks;
- C1–C5 теперь проходят Qt-независимое bounded conditioning до расчёта `TG_CALC`, относительных
  компонентов, Haworth и Pixler; исходные кривые не перезаписываются;
- Windows quality, GUI/HiDPI/PDF и security gates автоматизированы; реальная физическая печать,
  полевые interoperability и длительные soak gates остаются ручными/полевыми критериями;
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
- [ ] **GAS-05:** устранить дублирование правил между calculation conditioning и render sampling:
  вынести единый Qt-независимый continuity policy и единый segment mask для экрана, PDF,
  preview и принтера.
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

## P1 — поддерживаемая архитектура

- [x] **RULER-01:** единый Qt-независимый контракт глубинных/временных отметок, общей частоты и индивидуальной видимости колонок сериализуется в tablet layout v22; layouts v1–v21 получают безопасную миграцию.
- [x] **RULER-02:** настройки видимости и частоты внутренней шкалы подключены к существующему редактору графической колонки на RU/KK/EN и сохраняются в layout v22.
- [ ] **RULER-03:** экранный `TabletView` использует один resolved ruler и передаёт его точный набор значений/Y-координат всем глубинным и графическим колонкам; остаётся подключить тот же контракт к preview/PDF/printer и закрыть HiDPI/page-boundary tests.
- [ ] **RULER-04:** после стабилизации шкал завершить единый gas continuity/segment mask для C1–C5, relative gas, Haworth и Pixler.

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
