# История изменений

Здесь фиксируются только крупные продуктовые изменения. Подробная история отдельных исправлений
доступна в Git; отдельные release notes, build manifests и AI-отчёты не создаются.

## Unreleased

- Исправлен Windows Release gate: setup-uv теперь использует существующую опубликованную версию `0.11.29` вместо недоступной `0.11.32`; добавлен regression-контракт для всех трёх jobs.
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
