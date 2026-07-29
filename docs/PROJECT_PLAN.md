# Единый план проекта

<!-- runtime-contract: package=0.7.93; project=v22; form=v11; layout=v21 -->

Актуально на 28 июля 2026 года. Это единственный план проекта. Завершённая работа фиксируется
только в [CHANGELOG.md](CHANGELOG.md); инструкции и технические контракты не содержат отдельных
roadmap, build report или release plan.

## Текущая база

- пакет `0.7.93`; project `v22`; form `v11`; tablet layout `v21`;
- пользовательские project/LAS sidecars исключены из новых коммитов; опубликованная история
  Git требует отдельной согласованной очистки;
- WITS0, WITSML 1.4.1.1, WITSML 2.x/ETP foundation, GS2/Paradox, планшет, формы и отчёты
  реализованы, но реальные полевые interoperability/soak gates ещё не закрыты.

## Сравнение и принятые ориентиры

- [WellCAD](https://wellcad.com/) объединяет загрузку, редактирование, интерпретацию и
  представление vendor-independent borehole data, а
  [Automation API](https://wellcad.com/addon/automation/) открывает импорт, экспорт, печать и
  редактирование. Для проекта composition root выбран как целевая архитектура, а первым
  extension interface будет read-only versioned API; выполнение пользовательского кода при
  открытии проекта не принимается.
- [Techlog](https://www.software.slb.com/products/techlog?tab=Overview) сочетает real-time поток,
  междисциплинарные и multiwell workflows; его
  [versioned workflows](https://www.software.slb.com/software-news/support-news/techlog/techlog-2024-3)
  проверяют совместимость major version. Для проекта real-time reliability и versioned contracts
  идут раньше multiwell/3D.
- [Energistics](https://energistics.org/etp-developers-users) называет ETP 1.2 текущей версией
  для новых production implementations и отдельно предупреждает о несовместимости с ETP 1.1.
  Поэтому ETP/WITSML принимаются только через version/provenance envelope и реальную
  interoperability matrix.
- [Parquet column chunks](https://parquet.apache.org/docs/file-format/data-pages/columnchunks/)
  позволяют пропускать ненужные pages и независимо применять encoding/compression. Этот принцип
  принят для будущего chunked storage, но конкретный формат выбирается только после benchmark,
  crash-recovery и compatibility prototype.
- [OWASP File Upload](https://cheatsheetseries.owasp.org/cheatsheets/File_Upload_Cheat_Sheet.html)
  требует defense in depth и лимиты, а
  [XXE Prevention](https://cheatsheetseries.owasp.org/cheatsheets/XML_External_Entity_Prevention_Cheat_Sheet.html)
  — запрет DTD/external entities и resource limits. Эти требования закреплены в SEC-02/03 и
  Import Review.

## P0 — выпуск и безопасность

- [x] **REL-02:** добавлены Windows/Python 3.11 runtime lock с hashes, CycloneDX SBOM,
  dependency/secret/static scans и отдельные quality/security CI artifacts.
- [ ] **REL-03:** пройти Windows GUI/HiDPI/PDF/physical-printer matrix и сохранить checklist.
- [ ] **SEC-01:** согласовать очистку опубликованной Git history от пользовательского
  `project.geolog.json`, sidecars и inferred service author identities; проверить clones, caches,
  forks и releases.
- [x] **SEC-02:** ETP multipart ограничен суммарным encoded-объёмом, числом частей и временем
  сборки; превышение завершает pending requests и закрывает недоверенную сессию.
- [x] **SEC-03:** большие LAS/XML inputs переведены на streaming с ранними лимитами размера,
  глубины, элементов, текста и атрибутов; DTD/entity/external entity/notation блокируются до materialization.
- [x] **SEC-04:** WITS0 raw retention удаляет данные только из application-owned каталога с
  path-bound marker; remote server bind требует явного предупреждения, non-global CIDR allowlist
  и отбрасывает peers вне политики.
- [ ] **SEC-05:** завершить provenance/license review встроенных lithology/symbol assets и
  заменить vendor-specific labels там, где нет подтверждённого права и продуктовой необходимости.

## P0 — производительность и хранение

- [x] **PERF-01:** acquisition использует `append_many()` с batch 64, геометрические
  index/curve buffers, logical-length rollback и incremental record/dataset/events hash chains;
  полный projection digest выполняется только на checkpoint/current result.
- [ ] **PERF-02:** добавить checkpoint/replay без двойного хранения materialized Dataset и
  полного journal.
- [ ] **PERF-03:** закрепить benchmark 50k/100k/1M: `T(2N)/T(N) <= 2.5`, p95 batch64
  `<= 50 ms`, last/first 10k `<= 2`.
- [ ] **PERF-04:** внедрить revision-based tablet caches с byte budget и измерять cold/hit/zoom
  и peak RSS на 1/5/10 млн samples.
- [ ] **PERF-05:** заменить монолитный JSON save/open на совместимый versioned storage port:
  manifest, column chunks, atomic commit и crash recovery.

## P1 — поддерживаемая архитектура

- [ ] **ARCH-01:** создать `ApplicationContext`/composition root для storage, semantic, import,
  report, credentials и audit services.
- [ ] **ARCH-02:** разделить `MainWindow` на feature coordinators; запретить UI прямые записи в
  project collections, Dataset, layout и dirty-state.
- [ ] **ARCH-03:** вынести из `TabletView` sampling/cache, navigation, track lifecycle и editing
  state в Qt-независимые компоненты с transition tests.
- [ ] **ARCH-04:** внедрить один immutable `SemanticContext` во все importers и сохранять
  source mnemonic, UOM, mapping evidence и версию каталога.
- [ ] **ARCH-05:** закрепить границы слоёв AST/import-contract тестами.

## P1 — полевая совместимость

- [ ] **FIELD-01:** получить обезличенный WITS0 поток, выполнить reconnect/restart/disk-full и
  8–24-часовой Windows soak.
- [ ] **FIELD-02:** проверить WITSML 1.4.1.1 минимум на двух Store implementations.
- [ ] **FIELD-03:** выполнить ETP 1.2 matrix для реальных Store/producer: TLS/auth/proxy,
  paging, quality, reconnect, replay и subscription recovery.
- [ ] **FIELD-04:** проверить GS2/Paradox минимум на трёх обезличенных версиях и сравнить
  TIME/DEPTH, C1–C5, total gas, UOM, Gas Ratio и Pixler с эталонным export.
- [ ] **FIELD-05:** хранить standard/version/provenance envelope для WITSML 2.1/ETP 1.2,
  PWLS property kinds и Energistics UOM.

## P2 — расширение после P0/P1

- [ ] **EXT-01:** открыть versioned read-only API на immutable DTO/snapshots.
- [ ] **EXT-02:** разрешать изменения только через validated transactional commands с
  permissions, timeout, audit и rollback; не выполнять код при открытии проекта.
- [ ] **EXT-03:** multiwell correlation и общий PDF — только после performance/RSS gate.
- [ ] **EXT-04:** 3D и AI import требуют отдельных validation/provenance sections и gates внутри
  этого плана и не входят в ближайший выпуск.

## Критерий завершения задачи

Задача закрывается только когда одновременно обновлены код, regression test, нужные инструкции
RU/KK/EN, `CHANGELOG.md`, и пройдены применимые автоматические и Windows gates. Новые отдельные
планы, отчёты о сборках и versioned release-note файлы в `docs` не создаются.
