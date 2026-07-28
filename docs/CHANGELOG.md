# История изменений

Здесь фиксируются только крупные продуктовые изменения. Подробная история отдельных исправлений
доступна в Git; отдельные release notes, build manifests и AI-отчёты не создаются.

## Unreleased

- Закрыт PERF-01: acquisition применяет `append_many()` атомарными batch по 64 records, хранит растущие index/curve arrays в геометрических buffers, откатывает failed batch изменением logical length и ведёт incremental record/dataset/events hash chains; полный projection digest рассчитывается только для checkpoint/current result.
- Исправлен временной планшет после импорта GeoScape2/GS2: ширина DATETIME-оси теперь учитывается в общем canvas и групповых заголовках, статическое обновление не сжимает колонку времени, а dataset, форма и геологические слои устанавливаются одним render pass без остаточных Qt-виджетов.
- Закрыт SEC-04: WITS0 retention работает только в каталоге с проверенным path-bound application marker; непустой каталог требует явного принятия оператором. Non-loopback TCP server bind требует подтверждённого предупреждения, non-global IPv4 CIDR allowlist, отдельного разрешения для `0.0.0.0` и отклоняет peers вне политики.
- Закрыт SEC-03: LAS читается bounded streaming-блоками до запуска `lasio`, а WITSML 2.x inventory/data import и WITSML 1.4.1.1 SOAP используют единый streaming XML parser с ранними лимитами размера, глубины, элементов, текста и атрибутов; DTD/entity/external entity/notation блокируются callback-ами Expat.
- Исправлена оставшаяся Windows-специфика Release gate: golden-файлы сравниваются с нормализованными переводами строк, MIME DOCX определяется без Windows Registry, secret scan исключает только известные UI-метки, а GUI/PDF matrix запускается через headless Qt offscreen на Windows runner с гарантированно многостраничным continuation case.
- Исправлен Windows Release gate: репозиторные thumbnails конструктора больше не игнорируются Git; GUI tablet acceptance получает полный набор ресурсов; secret scan сохраняет структурированные детекторы и отключает только шумные Base64/Hex entropy-плагины.
- Исправлены ошибки следующего полного Windows Release gate: устранены три ошибки mypy,
  `QPdfDocument` ожидает асинхронный статус `Ready`, а исключения secret scan работают с
  Windows/Linux separators и не сканируют CI artifacts, golden outputs и явно синтетические fixtures.
- Исправлен Windows Release gate: для `websockets 16.1.1` в Windows/Python 3.11 release-lock закреплён SHA-256 wheel `cp311-win_amd64` вместо SHA-256 source archive; добавлен regression-контракт.
- Для воспроизводимости Windows Release gate `setup-uv` закреплён на action v8.1.0 и опубликованной версии `uv 0.11.29`; одинаковая конфигурация проверяется во всех трёх jobs.
- Закрыт SEC-02: профили ETP теперь задают лимиты суммарного encoded-размера multipart,
  количества частей и времени сборки; превышение лимита завершает pending requests и закрывает
  сессию, а audit сохраняет только безопасные счётчики и причину.
- Подготовлена автоматизируемая часть REL-03: Windows GUI/HiDPI/PDF matrix для
  100/125/150/200%, машиночитаемый checklist и отдельный CI artifact; physical-printer gate
  остаётся открытым до реального отпечатка и визуального подтверждения.
- Закрыт REL-02: добавлен hash-pinned runtime lock для Windows x86-64/Python 3.11, CycloneDX
  SBOM, dependency/secret/Bandit gate и отдельные Windows quality/security CI artifacts.
- Закрыт REL-01: backlog `mypy` сокращён с 234 ошибок до нуля, усилены runtime-контракты
  acquisition/ETP/WITS/WITSML/UI и стабилизирован Windows Qt lifecycle полного test gate.
- Проведён аудит поддерживаемости, производительности и безопасности.
- Усилены WITSML 1.4.1.1 SOAP TLS/redirect rules, XML/SVG parsing, Paradox allocation guards, sidecar
  integrity checks и spreadsheet formula neutralization.
- Ускорены current-project migration и tablet sampling/cache fast paths.
- Factory localization больше не перезаписывает пользовательские подписи.
- Документация сокращена до одного канонического плана, единого changelog и актуальных
  инструкций RU/KK/EN.
- Пользовательские project/LAS assets исключены из новых Git-коммитов; два старых результата
  ручной проверки удалены.
- GS2/Paradox документы и regression tests обезличены; зависимости от локальных
  user-provided verification files удалены.

## 0.7.93

- Runtime-переключение RU/KK/EN для стандартных форм, секций, технологических параметров и
  каталожных пород.
- Пользовательские подписи и свободные описания сохраняются без перевода.
- Project `v21`, form `v11`, tablet layout `v21`.

## Крупные этапы

- **0.7.80–0.7.83:** WITSML 1.4.1.1 read-only, WITSML 2.x/ETP 1.2 foundation,
  ETP acquisition и GeoScape WITS catalog.
- **0.7.73–0.7.79:** WITS0 raw capture, parser, Import Review, append-only acquisition,
  live view, recovery/soak tooling и offline WITSML import.
- **0.7.60–0.7.72:** compact tablet headers, form catalog, diagnostics, responsive toolbars
  и graph symbols.
- **0.7.31–0.7.59:** command/mutation boundaries, semantic dictionary, report pipeline,
  acquisition replay и editing stability.
- **0.7.16–0.7.30:** Paradox/GeoScape import, annotations, dataset workflows и tablet
  interaction architecture.
- **0.7.0–0.7.15:** universal workspace, LAS Editor, constructor, printing, form engine,
  stratigraphy and curve editing.
