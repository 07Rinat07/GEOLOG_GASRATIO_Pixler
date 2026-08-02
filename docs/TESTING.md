# Проверка качества и release gate

Документ актуален для **GEOLOG GASRATIO@Pixler 0.7.93** на 2 августа 2026 года. Краткая история
находится только в `CHANGELOG.md`; результаты конкретных CI/сборок хранятся как artifacts и не
заменяют текущие команды проверки.

Тест является контрактом продукта. Его нельзя ослаблять или пропускать только ради зелёного CI.
При осознанном изменении поведения одновременно обновляются production code, regression test,
единый план, архитектура, документация и changelog.

## 1. Подготовка окружения

Для повседневной разработки из корня проекта в Windows PowerShell:

```powershell
py -3.11 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -e ".[dev]"
```

Для release gate используется хешированный `requirements/release.lock`. Он содержит полный
runtime-граф распространяемого приложения для CPython 3.11 на Windows x86-64. Quality- и
security-инструменты не входят в состав приложения: workflow устанавливает их отдельно и только
в точно закреплённых версиях. Воспроизводимая установка runtime:

```powershell
uv venv .venv --python 3.11
uv pip sync requirements/release.lock --python .venv --require-hashes
uv pip install --python .venv --no-deps --no-build-isolation --editable .
```

Lock обновляется осознанным отдельным изменением после проверки diff:

```powershell
uv pip compile pyproject.toml `
  --python-version 3.11 `
  --python-platform windows `
  --generate-hashes `
  --output-file requirements/release.lock
```

Нельзя вручную удалять transitive requirements или hashes из готового lock-файла. После
обновления проверяются целевая платформа в заголовке, полный runtime-граф и diff каждого hash.
Локальное виртуальное окружение и кэш `uv` не входят в архив проекта.

Канонический запуск приложения:

```powershell
$env:PYTHONPATH = "$PWD\src"
python -m geoworkbench.app.main
```

Запуск через модуль является основным документированным сценарием. Консольные entry points из
`pyproject.toml` сохраняются для совместимости, но не заменяют эту команду в README и проверках.

## 2. Быстрый обязательный gate

Перед передачей архива или публикацией hotfix выполняются:

```powershell
python tools/check_documentation.py
python -m compileall -q src tests tools scripts
python -m pytest -q `
  tests/test_module_entrypoint_contract_0790.py `
  tests/test_test_runner_contract_0790.py `
  tests/test_documentation_sync_0762.py `
  tests/test_root_readme_scope.py `
  tests/test_release_security_contract.py `
  tests/test_windows_release_matrix_contract.py `
  tests/test_gs2_form_axis_hotfix_0789.py `
  tests/test_index_detection.py `
  tests/test_compact_geology_columns.py `
  tests/test_form_engine_models.py `
  tests/test_masterlog_presets.py
```

Этот набор проверяет:

- единый способ запуска `python -m geoworkbench.app.main`;
- соответствие версии пакета runtime-контракту документации;
- синхронность RU/KK/EN-документации и корректность внутренних ссылок;
- безопасное согласование TIME/DEPTH после импорта GeoScape2/GS2;
- сохранение линейной шкалы по умолчанию в формах и Masterlog-пресетах;
- отсутствие синтаксических ошибок в Python-модулях;
- контракт Windows GUI/HiDPI/PDF acceptance matrix и невозможность автоматически объявить
  физическую печать пройденной.

## 3. Расширенная проверка в headless-контейнере

Когда в среде нет PySide6, pyqtgraph или lasio, используйте:

```powershell
python scripts/run_headless_tests.py
```

Скрипт сначала выполняет collection всего набора. Он исключает файл только тогда, когда collection
заблокирован реально отсутствующим модулем из закрытого списка `PySide6`, `pyqtgraph`, `lasio`.
Любая другая collection-ошибка остаётся фатальной. Это диагностический reduced-environment gate,
а не замена полному Windows-прогону. Async ETP-тесты при этом выполняются через явно загруженный
`pytest_asyncio.plugin`.

## 4. Полный автоматический gate

В установленном Windows-окружении:

```powershell
$env:PYTHONUTF8 = "1"
python tools/check_documentation.py
python -m ruff check src tests tools scripts
python -m mypy src
python scripts/run_tests.py -p no:cacheprovider
```

Каждая команда должна завершиться с кодом `0`. Успешный выборочный набор не заменяет полный
прогон. Пропуски обязательных сценариев, зависание процесса, native crash Qt или изменённые
тестами файлы проекта считаются блокирующими дефектами.

UTF-8 фиксируется явно: иначе Windows console с CP1251 может аварийно завершить `mypy` при выводе
диагностики, содержащей символы единиц измерения, и замаскировать обычный type-check debt под
внутреннюю ошибку инструмента.

`scripts/run_tests.py` является штатной оболочкой полного pytest-прогона. Она отключает случайные
глобальные плагины, но явно загружает проектный `pytest_asyncio.plugin`, поэтому async ETP-тесты
не пропускаются. Оболочка сохраняет код результата тестов и изолирует завершение процесса от
нестабильной выгрузки нативных Qt DLL.

## 5. Security gate и CI artifacts

После установки окружения из lock-файла выполняется:

```powershell
python tools/release_security_gate.py
```

Команда запускает `pip-audit` в строгом hash-режиме, создаёт CycloneDX JSON SBOM, проверяет
исходный код через `detect-secrets` и запускает Bandit для `src`, `tools` и `scripts`. Результаты
пишутся только в игнорируемый каталог `build/ci-artifacts/security`:

- `dependency-audit.json`;
- `sbom.cdx.json`;
- `secret-scan.json`;
- `bandit.json`;
- `security-manifest.json` с SHA-256 lock-файла, командами и статусами.

Workflow `.github/workflows/release-gate.yml` отдельно выполняет Windows quality gate,
Windows GUI/HiDPI/PDF acceptance и Windows security gate. Логи качества, acceptance evidence
и security reports загружаются как три CI artifact с retention 30 дней. Artifact не коммитится
и не считается успешным gate, если соответствующая команда завершилась ненулевым кодом.

## 6. SEC-03: bounded LAS/XML inputs

Регрессия `tests/test_bounded_input_limits.py` проверяет раннее прекращение binary read, chunk size,
XML namespace/text/tail, запрет DTD/entity/notation и отдельные лимиты bytes, depth, elements,
text, attributes и attribute bytes. Интеграционные случаи подтверждают те же ограничения в
WITSML inventory и ChannelSet data import. `tests/test_las_adapter.py` проверяет, что oversized LAS
отклоняется до вызова `lasio`, а семантический parser получает уже проверенную in-memory копию.

Минимальный локальный запуск:

```bash
python -m pytest -q tests/test_bounded_input_limits.py tests/test_witsml_inventory.py \
  tests/test_witsml_data_arrays.py tests/test_witsml1411_soap.py tests/test_lossless_las.py
```

## 7. SEC-04: WITS0 ownership marker и remote-bind policy

`tests/test_wits0_reliability.py` проверяет fail-closed retention без marker, явное принятие
непустого каталога, отказ при повреждённом marker и невозможность авторизовать другой путь
скопированным marker. `tests/test_wits0_capture.py` проверяет loopback default, обязательные
warning acknowledgement и CIDR allowlist для non-loopback server, отдельное разрешение wildcard
`0.0.0.0`, запрет global/unbounded networks и фильтрацию peers политикой. UI contract проверяет
поля allowlist, warning и adoption flow.

Минимальный локальный запуск:

```bash
python -m pytest -q tests/test_wits0_reliability.py tests/test_wits0_capture.py \
  tests/test_wits0_capture_dialog.py
```

## 8. Автоматическая Windows GUI/HiDPI/PDF matrix

`tools/windows_release_matrix.py` запускается отдельным процессом для каждого Qt scale factor
`1.0`, `1.25`, `1.5` и `2.0`. Матрица проверяет A4/A3/roll, portrait/landscape, Fit/100%,
continuation pages, Unicode RU/KK/EN, инженерные символы, создание и повторное чтение PDF. Для
каждого случая сохраняются PDF, снимок тестового QWidget и `windows-release-checklist.json`.
Результаты создаются только в игнорируемом `build/ci-artifacts/windows-acceptance`.

Локальный запуск одного масштаба в Windows:

```powershell
python tools/windows_release_matrix.py `
  --scale-factor 1.25 `
  --platform windows `
  --output-dir build/ci-artifacts/windows-acceptance/1_25
```

CI запускает все четыре масштаба. Успешная автоматическая матрица получает общий статус
`pending_physical_printer`: наличие PDF и screenshots не доказывает реальную подачу бумаги,
цвет, clipping, поля драйвера и читаемость физического отпечатка.

## 9. Ручная Windows-приёмка GUI и физической печати

Автоматические source-contract, headless и Windows matrix не заменяют проверку настоящего
интерфейса и принтера. Минимальный smoke-сценарий:

1. Запустить приложение командой `python -m geoworkbench.app.main`.
2. Импортировать временную и глубинную таблицы GeoScape2/GS2.
3. Переключить вертикальную ось TIME/DATETIME ↔ DEPTH и проверить подписи шкалы.
4. Применить несколько заводских и пользовательских форм подряд.
5. Убедиться, что формы используют линейную шкалу по умолчанию и нулевые LAS-значения не
   разрывают кривую.
6. Сохранить проект, закрыть приложение, повторно открыть проект и повторить переключение формы.
7. Проверить планшет, аннотации, PDF, печать, внешний монитор и DPI 100/125/150%.

При ошибке нужно создать diagnostics ZIP через меню «Справка» и приложить его вместе со
скриншотом, исходным файлом и точной последовательностью действий.

Физический acceptance checklist фиксируется той же командой и считается пройденным только при
явном выборе принтера, фактической отправке задания и визуальном подтверждении оператором:

```powershell
python tools/windows_release_matrix.py `
  --scale-factor 1.0 `
  --platform windows `
  --output-dir build/ci-artifacts/windows-acceptance/physical `
  --printer "ТОЧНОЕ ИМЯ ПРИНТЕРА" `
  --operator "ФИО инженера" `
  --print-test `
  --confirm-physical-output `
  --require-physical
```

Команда последовательно проверяет и печатает A4, A3, custom и roll cases, включая все страницы
продолжения. Без `--print-test`, `--operator` и `--confirm-physical-output` инструмент не может
записать physical-printer status `passed`. Полученный checklist хранится как release artifact,
а не в Git.

## 10. PERF-01: acquisition batch/buffer/hash-chain contract

`tests/test_acquisition.py` проверяет default batch 64, отсутствие full projection digest во время
`append_many`, геометрический рост capacity, logical rollback mixed batch и детерминированное
восстановление incremental chain после replay. WITS0 и ETP runtime передают собственный
`drain_batch_size` в единый controller boundary.

Минимальный запуск:

```bash
python -m pytest -q tests/test_acquisition.py tests/test_wits0_acquisition.py \
  tests/test_etp12_acquisition.py tests/test_acquisition_codec.py
python benchmarks/benchmark_acquisition.py 50000 100000
```

Benchmark является диагностическим для PERF-01; обязательные scaling/p95/RSS thresholds остаются
отдельной незакрытой задачей PERF-03.

## 11. Регрессия GeoScape2/GS2 временного планшета

`tests/test_gs2_time_tablet_rendering.py` проверяет единый расчёт фактической ширины
DATETIME-колонки, canvas и групповых заголовков, а также один transactional render при смене
dataset. Qt-сценарий в `tests/test_tablet_view.py` подтверждает, что статическое обновление не
сжимает временную ось и не нарушает выравнивание треков.

Минимальный запуск:

```bash
python -m pytest -q tests/test_gs2_time_tablet_rendering.py \
  tests/test_gs2_form_axis_hotfix_0789.py tests/test_tablet_view.py
```

## 12. Газовый conditioning, расчёты и rendering

`calculations/gas_conditioning.py` является Qt-независимой границей подготовки C1–C5. Он обязан
сохранять source arrays, поддерживать increasing/descending/duplicate depth, интерполировать
только короткие bounded gaps и возвращать interpolation masks. После conditioning
`calculate_conditioned_ratios()` рассчитывает `TG_CALC`, относительные компоненты, Haworth,
изомерные отношения и Pixler. `ProjectSession` обновляет derived curves с versioned provenance.

Обязательный локальный набор:

```powershell
python -m pytest -q -p no:cacheprovider `
  tests/test_gas_conditioning.py `
  tests/test_project_session_gas_ratios.py `
  tests/test_gas_curve_rendering_continuity.py `
  tests/test_complex_gas_form.py `
  tests/test_a4_factory_templates.py
```

Контракты:

- source C1–C5 и depth не изменяются;
- mixed/nonfinite axis отклоняется;
- short gap восстанавливается, long/edge outage остаётся `NaN`;
- конечный zero не перезаписывается и разрывает logarithmic curve;
- duplicate-depth finite measurement имеет приоритет над missing row;
- C4/C5 не учитываются одновременно как aggregate и split family;
- сумма доступных `*_REL` равна 100% на валидной строке;
- zero denominator не создаёт infinity;
- recalculation сохраняет curve ID, повышает version и обновляет metadata/provenance;
- gas-only render policy не применяется к GR/ROP/DEXP;
- context points сохраняют сегмент на границе viewport/PDF page;
- screen/preview/PDF используют одинаковые derived arrays и segment semantics.

Ручной regression выполняется после повторной команды **«Рассчитать базовые Gas Ratio»** на
обезличенном интервале `1703.28–1753.28 м`. Старый PDF автоматически не обновляется.

Диагностический benchmark:

```powershell
python benchmarks/benchmark_gas_conditioning.py 100000 1000000 --repeats 3
python benchmarks/benchmark_gas_conditioning.py 100000 1000000 --repeats 3 --json
```

Benchmark измеряет conditioning семи компонентов и полный derived profile. Обязательные
scaling/RSS thresholds закрепляются после стабильного Windows baseline в задаче GAS-08; случайный
wall-clock assertion не добавляется в обычный unit suite.

## 13. GAS-05: единый continuity policy и segment mask

`tests/test_curve_continuity_policy.py`, `tests/test_gas_conditioning.py`, `tests/test_gas_curve_rendering_continuity.py` и `tests/test_tablet_gas_segment_mask.py` проверяют общий cadence policy, короткие и длинные пропуски, реальные нули, viewport/page context и явный PyQtGraph connect mask. Relative gas, Haworth, Pixler и source C1–C5 используют тот же экранный/печатный geometry path.

```powershell
python -m pytest -q tests/test_curve_continuity_policy.py tests/test_gas_conditioning.py tests/test_gas_curve_rendering_continuity.py tests/test_tablet_gas_segment_mask.py
```

## 14. Правило обновления тестов и документации

Любое изменение запуска, импорта, формы, миграции, расчётного профиля, формата проекта или
пользовательского поведения должно в одном инкременте обновлять:

- production code;
- positive/boundary/negative regression tests;
- `PROJECT_PLAN.md`, если изменились приоритеты, риск или статус задачи;
- `ARCHITECTURE.md`, если изменилась граница или источник истины;
- корневой README, если изменился запуск или базовый workflow;
- соответствующие RU/KK/EN-инструкции;
- `CHANGELOG.md`;
- `tools/check_documentation.py`, если новый контракт можно проверить автоматически.

Версия не считается готовой только по `compileall` или выбранным тестам. CI artifact должен
показывать реально выполненные проверки. После интеграции удаляются временные ветки, patch
workflow, trigger-файлы и artifacts.

## 15. Каталоги печатных шапок и логотипов

Минимальная доменная и SKF-проверка:

```bash
python -m pytest -q tests/test_header_catalog.py tests/test_logo_catalog.py \
  tests/test_project_logo_catalog_migration.py tests/test_masterlog_presets.py \
  tests/test_skf_importer.py
```

Полный Windows Release gate дополнительно проверяет Qt-диалоги, A4/A3 portrait/landscape,
многостраничный PDF, SVG/PNG assets и отсутствие регрессий существующих Masterlog/форм.
