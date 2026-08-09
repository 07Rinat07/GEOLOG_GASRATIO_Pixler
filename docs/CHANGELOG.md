# История изменений

Здесь фиксируются только крупные продуктовые изменения. Подробная история отдельных исправлений
доступна в Git; отдельные release notes, build manifests и AI-отчёты не создаются.

## Unreleased

- Комплексная газовая A4-форма приведена к отраслевому порядку integrated gas log:
  `Depth/ROP → C1–C5 → Total Gas → normalized C1–C5 → relative composition →
  Wetness/Balance/Character и изомеры → Pixler`. Полные `iC4/nC4/iC5/nC5` сохраняются,
  если присутствуют в источнике; единицы исходных ROP и газовых каналов не подменяются.
- Исправлена печать плотных шапок и короткой последней страницы: все семь строк C1–nC5 входят
  в верхнюю и повторную нижнюю шапку, а график не продолжается под ней. Проверка выполнена на
  реальных LAS, GS2 time и BLData и на synthetic seven-component regression.
- Off-scale значения больше не превращаются в `NaN`-острова: непрерывный сегмент проходит через
  ограниченную off-screen область и обрезается viewport/PDF, а реальные `NaN` и недопустимые
  logarithmic values остаются разрывами. Экстремальные выбросы ограничены безопасным overscan.
- Экран интерпретации получил явный сценарий `1. входы → 2. расчёт → 3. проверка →
  4. печать/экспорт`; шаг 4 открывает готовый отчёт и переводит фокус к печатным действиям.
- Объединены calculation и render continuity rules: C1–C5 и производные газовые кривые кондиционируются на полном общем depth basis, короткие sparse updates образуют линии через явный segment mask, а длинные остановки и реальные нули сохраняются как разрывы.
- Добавлен общий Qt-независимый контракт вертикальной шкалы и tablet layout v22: общий шаг задаётся один раз, а каждая графическая колонка может выбрать автоматический режим, цифры и риски, только риски или отключение и настроить частоту. Редактор и инструкции доступны на RU/KK/EN; колонка не может создать собственные значения глубины или Y-координаты.
- Введён Qt-независимый контур conditioning газовых данных: C1–C5 обрабатываются на неизменяемой
  рабочей копии до расчёта `TG_CALC`, относительных компонентов, Haworth, изомерных отношений и
  Pixler. Интерполируются только короткие bounded gaps; длинные остановки, края диапазона и
  измеренные нули сохраняются. Поддерживаются возрастающая/убывающая глубина и монотонные
  duplicate-depth rows, возвращаются interpolation masks и фактический max-gap по компоненту.
- `ProjectSession.calculate_basic_gas_ratios()` переведён на conditioned calculation profile
  `2.0`: исходные LAS-кривые не изменяются, повторный расчёт обновляет существующие derived curves,
  а provenance явно отличает новый workflow. Добавлены domain, session и rendering regression
  tests; обновлены единый план, архитектурный контракт, тестовая матрица и документация формы.
- Стандартный расчёт интерпретации создаёт видимые `C1_NORM`, reference-нормализованные C1–C5 и
  `TG_NORM` по явно показанным ROP/BIT/FLOW/E. Для разреженных тяжёлых компонентов доля C2–C5
  считается интегрально по интервалу. Готовые нормализованные кривые из LAS/GS2 распознаются и
  защищены от перезаписи.
- Интерпретация перспективных интервалов использует версионированную палетку Wh/Bh/Ch
  Haworth/DATALOG и диапазоны Pixler. Газ и ЛБА сопоставляются как согласованные, частично
  согласованные, расходящиеся или смешанные признаки без подмены заключения геолога.
- Каталог планшетных форм сокращён до недублирующих рабочих профилей. Для них добавлены A4-шапки
  portrait/landscape, автоматический выбор пары и опциональный повтор заголовков колонок.
- Добавлена комплексная газовая A4-форма C1–C5: абсолютные, суммарные, нормализованные и
  относительные газы, Haworth, изомеры и Pixler. В A4 виден один общий depth track, внутренние
  синхронные depth tracks сохранены.
- Во вкладке отчётов добавлена «Разгонка газовой смеси»: временная диаграмма C1–C5, фон, состав
  пробы, Wh/Bh/Ch, Pixler, предварительная категория, PDF/печать и компактный режим.
- Исправлена читаемость отчётов при тёмной системной теме.
- Добавлена вкладка «Отчёты по интерпретации»: безопасные Gas Ratio/Haworth/Pixler, `C1_NORM`,
  `DEXP/DEXPC`, поиск аномалий, предварительная интерпретация и XLSX/DOCX/PDF/print export.
- Отсутствие PyMuPDF/`fitz` в устаревшем `.venv` больше не блокирует запуск всего приложения;
  вкладка файлов показывает команду обновления зависимостей.
- Добавлена независимая вкладка «Файлы»: PDF/изображения, merge/split, DOCX, логотипы,
  безопасные архивы, инженерный калькулятор и расчёт datum/GL/wellhead/DF/RT/KB-RKB.
- Добавлен полноэкранный визуальный редактор шапок и форм с WYSIWYG, инспектором геометрии,
  адаптивными toolbar/overflow и исправленным SKF import.
- Добавлены раздельные каталоги печатных шапок и логотипов, factory Masterlog/суточные/
  технологические/аварийные шапки и выбор любой шапки для любой формы A4/A3.
- Исправлены разрывы временных кривых GeoScape2/GS2 и GeoScape/Paradox: sparse updates
  соединяются только в экранной геометрии, source NaN не изменяются, реальные time gaps остаются.
- Закрыт PERF-01: acquisition использует атомарный `append_many()` batch 64, геометрические
  buffers, logical rollback и incremental record/dataset/events hash chains.
- Исправлен временной планшет после импорта GS2: ширина DATETIME-оси, canvas и групповые заголовки
  согласованы, dataset/form/geology устанавливаются одним render pass.
- Закрыт SEC-04: WITS0 retention ограничен каталогом с application marker; non-loopback bind
  требует подтверждения и CIDR allowlist.
- Закрыт SEC-03: LAS/XML читаются bounded streaming-потоком; DTD/entity/external entity/notation
  блокируются до materialization.
- Стабилизирован Windows Release gate: line endings, MIME DOCX без Registry, secret scan,
  headless Qt matrix, thumbnails/resources, mypy, QPdfDocument и platform lock hashes.
- Закрыт SEC-02: ETP multipart ограничен размером, количеством частей и временем сборки.
- Подготовлена автоматическая часть REL-03: Windows GUI/HiDPI/PDF matrix для 100/125/150/200%;
  physical-printer gate остаётся ручным до фактического отпечатка.
- Закрыт REL-02: hash-pinned Windows x86-64/Python 3.11 runtime, CycloneDX SBOM,
  dependency/secret/Bandit gate и отдельные CI artifacts.
- Закрыт REL-01: mypy backlog сокращён до нуля, усилены runtime-контракты acquisition/ETP/WITS/
  WITSML/UI и стабилизирован Qt lifecycle полного Windows test gate.
- Проведён аудит поддерживаемости, производительности и безопасности; усилены TLS/redirect,
  XML/SVG, Paradox allocations, sidecar integrity и spreadsheet formula neutralization.
- Factory localization больше не перезаписывает пользовательские подписи; документация сокращена
  до одного канонического плана, changelog и синхронных инструкций RU/KK/EN.
- Пользовательские project/LAS assets исключены из новых коммитов; GS2/Paradox fixtures и
  regression tests обезличены.

## 0.7.93

- Runtime-переключение RU/KK/EN для стандартных форм, секций, технологических параметров и
  каталожных пород.
- Пользовательские подписи и свободные описания сохраняются без перевода.
- Project `v22`, form `v13`, tablet layout `v21`.

## Крупные этапы

- **0.7.80–0.7.93:** WITSML/ETP foundation, security/release gates, report pipeline, complex gas
  forms, print headers, HiDPI/PDF acceptance и архитектурная стабилизация.
- **0.7.73–0.7.79:** WITS0 raw capture, parser, Import Review, append-only acquisition,
  live view, recovery/soak tooling и offline WITSML import.
- **0.7.60–0.7.72:** compact tablet headers, form catalog, diagnostics, responsive toolbars
  и graph symbols.
- **0.7.31–0.7.59:** command/mutation boundaries, semantic dictionary, report pipeline,
  acquisition replay и editing stability.
- **0.7.16–0.7.30:** Paradox/GeoScape import, annotations, dataset workflows и tablet
  interaction architecture.
- **0.7.0–0.7.15:** universal workspace, LAS Editor, constructor, printing, form engine,
  stratigraphy и curve editing.
