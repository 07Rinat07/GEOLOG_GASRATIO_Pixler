# Проверка качества и release gate

`tests/test_masterlog_description_unicode.py` covers 45 actual-text font/PDF regressions
(three geology text paths × RU/KK/EN × 72/96/144/300/600 DPI) and three production
exports after package reopen. It verifies localized text without legacy/HTML leakage,
resolved font families after UI font changes, unchanged requested 6.5/6.0 pt sizes,
72-DPI extracted font/geometry baseline and preserved geology/source arrays. Existing
`tests/test_masterlog_renderer.py` guards rich-text alignment and bounded interval clipping.

Masterlog Unicode legends: `tests/test_masterlog_legend_unicode.py` checks 45 real
PDF cases (RU/KK/EN × 72/96/144/300/600 DPI × populated/empty lithology/LBA).
It changes the UI font, verifies actual text/font stack, a 3 mm body size and painter
restoration. Three production exports after package save/reopen verify localized legends
and unchanged forms/source arrays. Fractional pre-transform sizes retain existing Qt
rounding; these tests do not assert that native font quantization has been eliminated.

```powershell
python scripts/run_tests.py -q -p no:cacheprovider tests/test_masterlog_legend_unicode.py tests/test_masterlog_header_visual_profile.py tests/test_masterlog_control_layout.py tests/test_masterlog_renderer.py
```

Документ актуален для **DIGITAL GEOLOG GASRATIO&PIXLER 0.7.93** на 9 сентября 2026 года. Краткая история
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

### Диагностика завершения GUI-процесса

Ненулевой код запуска сам по себе не устанавливает причину. Штатный runner при сбое
дочернего процесса выводит `Test subprocess failed`, точные pytest selectors и код
завершения в десятичном/шестнадцатеричном виде. Исходный код возврата сохраняется;
проверки не пропускаются и автоматического повтора, скрывающего падение, нет.
Для диагностики сохраняйте весь журнал, а не только строки с `FAILED`:

```powershell
python scripts/run_tests.py -p no:cacheprovider *> pytest-diagnostic.log
$testExit = $LASTEXITCODE
Get-Content pytest-diagnostic.log -Tail 60
Write-Host "Test exit code: $testExit"
```

Успешный отдельный повтор не доказывает устранение причины предыдущего сбоя:
нужно также проверить полный штатный прогон.

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

Сквозной сценарий переносимого многоязычного проекта и суточного LAS запускается отдельно:

```powershell
.\.venv\Scripts\python.exe -m pytest -q -p no:cacheprovider `
  tests/test_multilingual_geologpkg_workflow.py
```

Он использует `tests/fixtures/las_sync`: первый LAS, допустимый суточный append и конфликтующий
LAS. Проверяются RU/KK/EN, reopen, duplicate no-op, конфликт без мутации, три PDF и копирование
одного `.geologpkg` в каталог «другого компьютера».

### RPT-COMP-01: persisted report composition

Проверка project-format v37 и UI restore boundary:

```powershell
python -m pytest -q -p no:cacheprovider tests/test_report_composition_persistence.py
```

Regression подтверждает JSON/`.geologpkg` round-trip, безопасную миграцию v36 с пустой
composition, отказ от ссылок на неизвестный dataset и восстановление orientation/order/
Auto-Show-Hide в report layout dialog. Composition является presentation state и не меняет
source LAS, расчётные series или geological records.

`tests/test_report_annotations.py` дополнительно проверяет отказ загрузки annotation schema
с JSON boolean, float, string, null и неподдерживаемыми целочисленными версиями. Валидная
целочисленная v1 сохраняется через существующие JSON/package round-trip regressions.

### RPT-COMP-01: saved chart columns

`tests/test_report_chart_panel_composition.py` проверяет JSON/package controller save/reopen,
legacy v37 defaults, bounded malformed settings, RU/KK/EN dialog restore/reorder/Cancel,
standard/OPUS default order, фактические preview/PDF painters и все скрытые колонки.
Проверяется неизменность source arrays/dataset fingerprint и отсутствие переноса аннотации
скрытой колонки к соседней. System print использует тот же подготовленный PDF и settings.

### Проверка состояния daily LAS preview (WELL-02)

Проверка привязки daily LAS preview к состоянию данных (первый инкремент WELL-02):

```powershell
python scripts/run_tests.py -q -p no:cacheprovider tests/test_daily_las_growth.py tests/test_daily_las_growth_dialog.py tests/test_proj04_daily_append_rollback.py tests/test_daily_las_growth_autosave.py
python -m benchmarks.benchmark_daily_las_preview
```

Проверяются изменения вне перекрытия, единицы, локальные кривые, отказ без мутации, повторный
анализ, отмена/ошибка окна, autosave и совместимость исторического audit SHA-256.
Benchmark измеряет только fingerprint 100k/1M, с лимитом временных выделений 4 MiB.

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

`a4-portrait-fit` дополнительно рендерит тот же REL-03/CUT-03 acceptance sheet, который используется
при физической печати: длинный rich-text, границы интервала, простой LBA, цвет и детерминированное
cuttings image через production `AnnotationRecord(kind=IMAGE)` / `TabletAnnotationItem` image
renderer. Это проверяет production image paint path в PDF, но не заменяет осмотр бумаги.

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

Физический acceptance checklist фиксируется той же командой. `passed` допустим только после
реальной отправки всех cases на принтер и отдельного подтверждения каждого визуального критерия
после осмотра бумаги. Полный операторский порядок: [PHYSICAL_PRINT_ACCEPTANCE.md](PHYSICAL_PRINT_ACCEPTANCE.md).

```powershell
python tools/windows_release_matrix.py `
  --scale-factor 1.0 `
  --platform windows `
  --output-dir build/ci-artifacts/windows-acceptance/physical `
  --printer "ТОЧНОЕ ИМЯ ПРИНТЕРА" `
  --operator "ФИО инженера" `
  --print-test `
  --confirm-rich-text `
  --confirm-cuttings-photo `
  --confirm-custom-heading `
  --confirm-interval-bounds `
  --confirm-color `
  --confirm-driver-margins `
  --confirm-no-driver-warning `
  --confirm-physical-output `
  --physical-notes "модель принтера, бумага/лоток, замечания" `
  --require-physical
```

Команда последовательно проверяет и печатает A4, A3, custom и roll cases, включая все страницы
продолжения. Без `--print-test`, `--operator`, всех семи `--confirm-*` evidence flags и финального
`--confirm-physical-output` инструмент не может записать physical-printer status `passed`.
Полученный checklist хранится как release artifact, а не в Git.

## 10. PERF-01…04: acquisition и tablet performance contracts

`tests/test_acquisition.py` проверяет default batch 64, отсутствие full projection digest во время
`append_many`, геометрический рост capacity, logical rollback mixed batch и детерминированное
восстановление incremental chain после replay. WITS0 и ETP runtime передают собственный
`drain_batch_size` в единый controller boundary.

`tests/test_acquisition_replay_memory.py` закрепляет PERF-02: fresh replay не выполняет
`deepcopy(Well)` и не копирует unrelated datasets; checkpoint resume staging копирует только один
изменяемый acquisition Dataset, а immutable journal/checkpoints/events переиспользуются через
новые контейнеры без ослабления transactional rollback.

`tests/test_acquisition_benchmark.py` проверяет логику PERF-03 guardrails: nearest-rank p95,
обязательный batch64, `T(2N)/T(N) <= 2.5`, p95 `<= 50 ms` и last/first `<= 2`. Сам wall-clock
performance не помещается в обычный unit suite: enforcing runner выполняется Windows quality gate
на `50k/100k/1M` и сохраняет JSON artifact.

`tests/test_geometry_cache_byte_budget.py` закрепляет PERF-04: точный `numpy.nbytes` accounting,
LRU eviction по byte budget и entry count, MRU promotion после hit, oversize geometry без
retention, освобождение bytes при clear/invalidate и независимые revision keys. Тест также
проверяет read-only sampled arrays. `tests/test_curve_sampling_benchmark.py` выполняет малый
production-seam cold→hit→zoom worker и проверяет structural benchmark contract.

Минимальный correctness-запуск:

```bash
python -m pytest -q tests/test_acquisition.py tests/test_acquisition_replay_memory.py \
  tests/test_acquisition_benchmark.py tests/test_geometry_cache_byte_budget.py \
  tests/test_curve_sampling_benchmark.py tests/test_wits0_acquisition.py \
  tests/test_etp12_acquisition.py tests/test_acquisition_codec.py
```

Воспроизводимые performance-runs:

```powershell
python benchmarks/benchmark_acquisition.py --json
python benchmarks/benchmark_curve_sampling.py --json
```

Quality gate сохраняет PERF-03 как
`build/ci-artifacts/quality/acquisition-benchmark.txt`. Каждый размер запускается в отдельном
worker-процессе; p95 и first/last сравниваются по полным batch64. Batch-aligned окно содержит
`157 × 64 = 10 048` строк, поэтому partial tail не искажает последнюю метрику. Peak RSS
фиксируется для наблюдения, но PERF-03 не задаёт отдельный RSS threshold.

Принятый Windows baseline PERF-03 release-gate #886: 50k/100k/1M —
`3.504 / 7.027 / 70.605 s`, p95 batch64 — `4.684 / 4.663 / 4.640 ms`, last/first —
`1.017 / 1.008 / 0.988`; `T(100k)/T(50k)=2.005`, violations отсутствуют.

PERF-04 сохраняется как `build/ci-artifacts/quality/curve-sampling-benchmark.txt`. Runner
изолирует 1M/5M/10M samples в отдельных процессах и для каждого выполняет cold miss, O(1) cache
hit и zoom miss при `max_points=4096`, одновременно проверяя `current_bytes <= max_bytes`.
Принятый Windows baseline release-gate #894: cold `43.049 / 161.581 / 289.547 ms`, hit
`0.0038 / 0.0036 / 0.0034 ms`, zoom `27.797 / 106.746 / 197.813 ms`, peak RSS
`84.5 / 302.1 / 574.2 MiB`. Во всех сценариях две cached geometry занимают `131 072 B` из
hard budget `67 108 864 B`.

### RPT-GAS-VIS-01: ratio scatter presentation

Газовые отношения и интерпретационные коэффициенты проверяются как дискретные point-series
без соединяющей линии, а обычные глубинные газовые кривые сохраняют line presentation:

```powershell
python -m pytest -q -p no:cacheprovider \
  tests/test_gas_curve_rendering_continuity.py \
  tests/test_tablet_gas_segment_mask.py \
  tests/test_tablet_view.py \
  tests/test_tablet_print_quality.py \
  tests/test_masterlog_renderer.py \
  tests/test_interpretation_report_charts.py \
  tests/test_gas_07_golden_acceptance.py
```

Shared predicate покрывает Haworth/WH-BH-CH, C1/C2…C1/C5, isomer ratios, Pixler и OPUS
ratio-series. Он намеренно исключает C1–C5/iso-normal components, TG/normalized gas,
`OPUS_TG_PCT` и `*_REL`. Tablet regression требует `symbol="o"` и отсутствие polyline
для ratio даже после STYLE-refresh; обычный C1/TG и ROP/DEXP сохраняют линии. Tablet print
может увеличить размер ratio marker, но не создаёт линию. Masterlog и hydrocarbon PDF/PNG
проверяют тот же glyph contract. C1–C5 ramp-report остаётся линейным временным профилем,
а relative-gas `*_REL` сохраняет cumulative 0–100% stacked fill. Расчётные массивы,
sampling/range и source LAS этим контрактом не меняются.


Windows quality gate дополнительно изолирует `tests/test_session_safety.py` по одному test node
на процесс. Это не ослабляет тесты: после воспроизводимого `0xC0000005` в
`pyqtgraph.ViewBoxMenu` файл исключён из длинного shared Qt shard, а
`tests/test_test_runner_contract_0790.py` проверяет наличие всех пяти test nodes как отдельных
native batches. Python assertion failures и ненулевые exit status по-прежнему немедленно
останавливают gate.

### REPORT-I18N-01: atomic RU/KK/EN report language

Office-export boundary проверяется отдельно от численных расчётов:

```powershell
python -m pytest -q -p no:cacheprovider `
  tests/test_report_i18n_atomic_language.py `
  tests/test_readable_interpretation_export.py `
  tests/test_hydrocarbon_report_client_limitations.py
```

Regression требует, чтобы выбранный язык workspace явно передавался в XLSX/DOCX; polished
Word cover и body использовали один язык; export progress и missing-value Haworth/DEXP labels
не возвращались к русскому fallback в KK/EN. Проверка содержимого выполняется по фактическому
`word/document.xml`, а не только по UI captions. Численные значения и report model этим
контрактом не изменяются.

### PERF-07: LAS import, first render и viewport baseline

Correctness coverage for the large-LAS profiling boundary:

```powershell
python -m pytest -q -p no:cacheprovider `
  tests/test_process_metrics.py `
  tests/test_las_adapter.py `
  tests/test_dataset_import_jobs.py `
  tests/test_main_window.py
```

The tests preserve the existing `las.import.performance` timing contract and verify RSS checkpoints
without exposing source values/full paths. PERF-07 additionally requires non-negative
`parse_stream_setup_ms`, `parse_lasio_ms` and `parse_index_ms`; these are observational
subphases of the existing `parse_ms`, not independent parser semantics or release thresholds.
The end-to-end benchmark carries the same fields into the Windows quality artifact. For the numeric fast-path
slice the clean PERF-07 fixture must report `parse_backend=numpy-loadtxt`; integration tests verify
NULL replacement, positional curve assignment and a `WRAP=YES` compatibility fallback that performs
the established full lasio read. Unsupported/malformed layouts must fail closed to that fallback rather
than partially accepting a fast matrix. Job-level tests guard the ordered
`job_load → policy → review → register → total` phases and failure-stage metrics. Main-window
tests verify both successful presentation and the existing fail-safe recovery path emit
`las.import.presentation` with duration/RSS. Memory collection is best-effort and cannot fail an
otherwise valid import. These metrics are observational; performance thresholds require a measured
Windows baseline rather than unit-test wall-clock assertions.

The first presentation-coalescing regression is intentionally separate from the LAS metrics:

```powershell
python -m pytest -q -p no:cacheprovider `
  tests/test_presentation_refresh.py `
  tests/test_tablet_partial_title_refresh_source.py
```

It verifies typed intent merging/reset semantics and guards that drag-width/drag-order handlers
schedule Project Tree + window-title refresh instead of calling them synchronously. The width drag
must still use the immediate `DirtyReason.STATIC` track refresh. No test permits coalescing
Dataset replacement, Undo/Redo, import presentation, or a full TabletView rebuild.

Visible-depth refresh regression:

```powershell
python -m pytest -q -p no:cacheprovider `
  tests/test_main_window_visible_depth_refresh.py `
  tests/test_main_window.py::test_curve_metadata_history_refresh_preserves_tablet_track_widgets `
  tests/test_tablet_view.py::test_curve_metadata_refresh_updates_headers_and_membership_in_place
```

The manual range case must keep `DirtyRenderStats.full_updates` and `partial_updates` unchanged
while the displayed/layout range changes in place. Reset must increment `full_updates` exactly
once, preserving the existing default-range resolution, and neither path may rebuild Project Tree.
Curve-metadata history regression additionally requires unchanged `full_updates`, stable track
widget identity and in-place header/unit refresh across Undo/Redo. TabletView metadata regression
also covers mnemonic rename reconciliation without restoring the full widget tree.

End-to-end PERF-07 regression and canonical Windows runner:

```powershell
python -m pytest -q -p no:cacheprovider tests/test_perf07_las_tablet_pipeline.py
python benchmarks/benchmark_las_tablet_pipeline.py --json
```

Обычный unit test использует малый temporary LAS (1000 строк, 8 кривых, 4 видимых track) и
проверяет production import → `TabletView.set_layout_and_dataset()` → scroll → zoom. Он не
содержит wall-clock assertions. Default benchmark использует M-1-shaped fixture: 27 500 строк,
351 data curve, 16 visible curve-track и viewport 1600×900. Release gate сохраняет JSON как
`build/ci-artifacts/quality/las-tablet-pipeline-benchmark.txt`.

Structural gate требует ровно один full rebuild для первого presentation и ноль дополнительных
`DirtyRenderStats.full_updates` на scroll/zoom. `tablet.render.full.finished` дополнительно
содержит `duration_ms`, start/end RSS и peak RSS.

Принятый Windows baseline Release gate #2297 на PR #423: import `12 484.34 ms`, first render
`629.01 ms`, scroll `60.29 ms`, zoom `109.67 ms`; navigation не увеличила full-render counter.
Release gate #2299 затем разложил import на source `809.28 ms`, parse `5 957.19 ms`,
Dataset materialization `14 263.00 ms`, report `44.68 ms`, подтвердив materialization как
крупнейшую фазу.

Текущий regression contract требует наличие неотрицательных subphase metrics:
`dataset_setup_ms`, `dataset_curve_values_ms`, `dataset_curve_canonical_ms`,
`dataset_curve_semantic_ms`, `dataset_curve_store_ms`, `dataset_headers_ms`. Эти метрики
наблюдательные и не меняют import semantics. Следующая оптимизация допускается только после
Windows materialization-subphase baseline.

Release gate #2301 локализовал bottleneck в `dataset_curve_values_ms` (13.89 s из 14.09 s).
Регрессия `test_import_las_materializes_lasio_data_matrix_once` использует test double с
счётчиком computed `data` property и требует ровно одно обращение на импорт при корректных
значениях всех curve columns. Это структурный guardrail против возврата O(curves × full-matrix)
работы; hardware-dependent timing assertion не используется.

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

## 13A. ОПУС: формулы, автоматическая интерпретация и паспорт методики

Минимальная проверка отдельного режима ОПУС и одинакового содержания отчётов:

```powershell
python -m pytest -p no:cacheprovider -q tests/test_opus_screening.py tests/test_hydrocarbon_interpretation.py tests/test_interpretation_report_charts.py tests/test_interpretation_report_identity.py
```

Набор закрепляет следующие контракты:

- равенство результатов для эквивалентных входов в `% об.` и ppm;
- четыре контрольные формулы и отсутствие `OPUS5_REF` в runtime/экспорте;
- классификацию только по отсчётам выше порога аномалии;
- единственное пересечение перекрывающихся диапазонов и отказ от класса вне профиля;
- явную цепочку ОПУС → Haworth/Pixler → неопределённый тип;
- сохранение найденных интервалов при низком фоне с отдельной отметкой применимости;
- одинаковые ОПУС-кривые на экране и в PDF и полный ряд глубин в XLSX;
- наличие в HTML/PDF, DOCX и XLSX формул, правил интерпретации, источников и степени
  подтверждения методики.

## 13B. Профиль «ОПУС Газомер»

Этап `OPUS-01` закреплён в `tests/test_opus_gasomer_fixture.py`: primary-workbook SHA,
контрольная строка, пять формул, каждая граница ниже/на/выше, явная errata AB4 и уникальная
мода без произвольного разрешения ничьей. `tests/test_opus_gasomer_batch.py` закрепляет
`OPUS-02`: ppm/% equivalence, синхронный независимый TotalGas, LOD boundary, missing/zero/
below-LOD/invalid states, зависимости отдельных показателей и неизменность source arrays.
`tests/test_opus_gasomer_interval.py` закрепляет `OPUS-03`: уникальную поддержку по
синхронным строкам, ничью интервала, QC/vote distributions, explicit maximum span и
доказательство синтетического legacy-состава из разных глубин.
`tests/test_opus_gasomer_detector.py` закрепляет `OPUS-04`: низкий фон без hard gate, отсутствие
ложного события на ровном фоне, смену локального фона, ppm/% equivalence, обязательный LOD,
монотонную прямую/обратную глубину и сохранение missing/invalid states.
`tests/test_opus_gasomer_report.py` закрепляет `OPUS-05/06`: отдельный TotalGas и явный LOD,
готовый report snapshot с прямым классом/support, пятью голосами/QC и provenance, одинаковые
формулы/класс в HTML, XLSX, DOCX, PDF и print HTML, неизменность исправления
`AB2>AB5=250000` → `AB2>=250000`, а также запрет скрытого detector LOD.
`tests/test_opus_gasomer_performance_contract.py` и
`benchmarks/benchmark_opus_gasomer.py` закрепляют `OPUS-07`: chunked regular-axis fast path,
physical-window fallback для нерегулярной оси, 25k/100k/1M и additional traced peak memory.

Воспроизводимый performance-run:

```powershell
python benchmarks/benchmark_opus_gasomer.py 25000 100000 1000000 --json
```

Контрольный Windows/Python 3.11 run 30 августа 2026 года:

| Строк | Batch, с | Detector, с | Batch peak, MiB | Detector peak, MiB |
|---:|---:|---:|---:|---:|
| 25 000 | 0,024 | 0,293 | 5,1 | 64,6 |
| 100 000 | 0,034 | 0,841 | 18,5 | 67,9 |
| 1 000 000 | 0,381 | 8,168 | 185,0 | 118,6 |

Traced peak не включает уже созданные source arrays. От 100k к 1M batch/detector дали
11,28×/9,72× времени при росте данных 10×; retained/result arrays растут линейно, а временный
rolling block ограничен по числу window elements. Пересчёт при PDF/печати запрещён report
snapshot-контрактом и проверяется экспортным тестом.

Дальнейшая полевая проверка:

1. confusion matrix на независимых интервалах ГИС/испытаний;
2. анализ false positive/false negative и отдельная версия полевой калибровки.

Полевой acceptance выполняется отдельно на обезличенных интервалах с независимым заключением
ГИС/испытаний. Для каждого класса строится confusion matrix и анализируются false positive и
false negative. До этого автоматический результат называется предварительным скринингом.
Подробные ожидаемые значения и порядок этапов:
[OPUS_GASOMER_IMPLEMENTATION.md](OPUS_GASOMER_IMPLEMENTATION.md).

## 13C. WITS operator workspace, live calculations and alarms

Для WITS-UX/CALC/GASCTX/ALARM/INTERP обязательны отдельные уровни проверки:

- **headless forms:** roundtrip Save/Reset по canonical mnemonic; новый Dataset/curve ID не ломает
  выбор; factory template не мутируется;
- **Qt adaptive:** форма выбирается до runtime, sidebar collapse, fullscreen → back, LIVE PREVIEW →
  persistent handoff, DPI 100/125/150/200%;
- **derived parity:** WH/BH/CH, Pixler и DEXP/DEXPC live результат совпадает с batch calculation
  на одинаковом интервале; проверяются missing inputs, NaN/zero и UOM conversion;
- **gas context:** background baseline не обучается connection/trip/circulation spikes;
  formation_show требует stable drilling + excursion; отсутствие контекста даёт
  elevated_unclassified;
- **interpretation markers:** line/band остаётся на исходной axis coordinate, badge может
  визуально смещаться; одинаковые соседние классы объединяются; overlapping labels не перекрываются;
- **alarms:** min/max boundary, hysteresis, debounce/minimum-duration, acknowledgement, mute,
  restart persistence и отсутствие repeated audio на каждом sample;
- **performance:** live-derived + alarms остаются bounded по памяти и не добавляют O(N²) на redraw;
- **field acceptance:** anonymized real GSWITS, reconnect/reopen, connection/trip events и
  подтверждение специалистом ГТИ, что fluid screening не смешан с gas origin.

## 13D. Формульный аудит, печатный стиль и флюид-выноски

Обязательные regression-gates для CALC-AUDIT-01 / PRINT-STYLE-01 / REPORT-ANNOT-01:

- все профили из `build_all_sourced_formula_registry()` присутствуют в method audit manifest;
- Haworth/Pixler/DEXP/DEXPC остаются strict primary/publication verified;
- ОПУС допускает `secondary_crosscheck` / `workbook_reproduced`, а detector defaults —
  только `engineering_default` pending field calibration;
- Report Passport для sourced calculation сохраняет formula id/version/provenance,
  expression hash и source;
- canonical print wordmark — **DIGITAL GEOLOG GASRATIO&PIXLER** — одинаков в PDF, Masterlog,
  DOCX/XLSX и PDF creator metadata;
- `tests/test_product_branding.py` дополнительно запрещает полный canonical wordmark literal во всех `src/**/*.py`, кроме `geoworkbench/brand.py`, чтобы новые adapters не создавали второй source of truth;
- polished interpretation DOCX проверяется с подменённым `ReportVisualProfile`: production OOXML обязан использовать semantic accent/text/muted colours, title/body/table sizes, table header fill и border roles из профиля;
- Masterlog neutral-chrome regression подменяет `ReportVisualProfile` и проверяет реальные
  QPainter page/accent-soft placeholder fills и text/border/border-strong/critical pens; lithology,
  stratigraphy, LBA, user curve и annotation/callout colours остаются отдельными semantics;
- fluid callout явно содержит тип флюида, а ambiguous/no-consensus не превращается в
  искусственно выбранный gas/oil class;
- dense adjacent callouts остаются внутри track bounds; для A4/A3 выполняются visual/PDF
  regression и grayscale-проверка;
- цвет не является единственным признаком: текстовая подпись должна сохранять смысл
  после grayscale/monochrome печати.

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

Для composition-root контракта ARCH-01 минимальный regression-набор:

```bash
python -m pytest -q tests/test_application_context.py tests/test_application_context_ui_wiring.py \
  tests/test_etp12_dialog_typing.py tests/test_witsml1411_soap.py
```

Он проверяет отдельный project scope, process-wide registry/report services, DI credentials/audit
для WITSML/ETP и production MainWindow wiring. Полный Release gate остаётся обязательным.

Для первого feature-coordinator инкремента ARCH-02:

```bash
python -m pytest -q tests/test_witsml_import_coordinator.py \
  tests/test_witsml_project_import_controller.py tests/test_witsml_import_dialog_source.py
```

Набор фиксирует автоматический выбор target well, атомарную регистрацию уже проверенного commit
и source-contract, запрещающий MainWindow напрямую создавать WITSML project-mutation controller.

Для второго ARCH-02 инкремента:

```bash
python -m pytest -q tests/test_lag_correction_project_controller.py \
  tests/test_lag_correction_ui_source.py
```

Набор проверяет source/projection selection, восстановление исходной projection только при
неизменённом выборе, typed missing-source failure и отсутствие прямой записи
`current_dataset_id` из MainWindow.

Для третьего ARCH-02 инкремента:

```bash
python -m pytest -q tests/test_gas_ratio_project_controller.py \
  tests/test_project_session_gas_ratios.py
```

Набор проверяет conditioned Gas Ratio/Haworth/Pixler persistence, controller rebinding,
совместимый session shim и source-contract, запрещающий MainWindow напрямую вызывать mutating
`ProjectSession.calculate_basic_gas_ratios()`.

Для четвёртого ARCH-02 инкремента:

```bash
python -m pytest -q tests/test_gs2_import_coordinator.py \
  tests/test_dataset_import_jobs.py tests/test_proj04_gs2_source_registry.py
```

Набор проверяет GS2 enrichment/registration, provenance source registry, отсутствие прямых
Dataset-записей в обоих слоях MainWindow и отсутствие второго production `open_gs2()`.

Для пятого ARCH-02 инкремента:

```bash
python -m pytest -q tests/test_canvas_object_transfer_coordinator.py \
  tests/test_canvas_object_transfer_mainwindow.py \
  tests/test_canvas_object_transfer_workflow.py
```

Набор проверяет transactional material autosave, session rebinding, invalidation старого review
и source-contract, запрещающий production UI создавать canvas controller/workflow вручную.

Для шестого ARCH-02 инкремента:

```bash
python -m pytest -q tests/test_late_analysis_coordinator.py \
  tests/test_late_analysis_review_dialog.py \
  tests/test_well_analysis_update_workflow.py
```

Набор проверяет source load, WELL-02 apply/material autosave, completion count, project rebinding,
инвалидацию старого review и отсутствие ad-hoc controller/workflow в production MainWindow.

Финальный ARCH-02 mutation boundary:

```bash
python -m pytest -q tests/test_arch02_ui_mutation_boundary.py
```

AST/source-contract запрещает прямые assignments и mutating calls к ProjectSession/project
collections/Dataset/Well из обоих MainWindow-слоёв и проверяет наличие утверждённых feature
coordinators. Полный Release gate остаётся обязательным перед merge.

Первый ARCH-03 state extraction:

```bash
python -m pytest -q tests/test_curve_pencil_state.py tests/test_tablet_edit_pipeline.py
```

Набор проверяет Qt-независимые transitions Curve Pencil и совместимость существующего TabletView
edit pipeline. Полный Release gate остаётся обязательным перед merge.

Второй ARCH-03 navigation extraction:

```bash
python -m pytest -q tests/test_tablet_navigation_coordinator.py
```

Набор проверяет projection visible range → scrollbar state, full-range collapse, обратное
scrollbar → visible range преобразование и существующие pan/zoom/keyboard transitions.

Третий ARCH-03 interval editing extraction:

```bash
python -m pytest -q tests/test_interval_editing_state.py tests/test_tablet_edit_pipeline.py
```

Набор проверяет mode/default-type transitions, lifecycle CREATE/RESIZE gesture и source-contract,
что `TabletView` делегирует editing-session state Qt-независимому компоненту.

Четвёртый ARCH-03 selection-state extraction:

```bash
python -m pytest -q tests/test_selection_interaction.py
```

Набор проверяет единый interval-selection source of truth в `SelectionManager`, active
interpretation context и source-contract на отсутствие параллельных selected-id полей в `TabletView`.

Пятый ARCH-03 render-state extraction:

```bash
python -m pytest -q tests/test_tablet_render_state.py \
  tests/test_tablet_geometry_cache.py tests/test_tablet_overlay_layers.py
```

Набор проверяет ownership geometry/static caches, dirty invalidation и отсутствие прямого
mutable render-state ownership в `TabletView`.

Финальный ARCH-03 tablet-state boundary:

```bash
python -m pytest -q tests/test_arch03_tablet_state_boundary.py
```

AST/source-contract проверяет отсутствие legacy mutable state в `TabletView.__init__`, наличие
утверждённых headless state/coordinator components, stateless sampling boundary и отсутствие
PySide6/pyqtgraph top-level imports в ARCH-03 state modules.

Первый ARCH-04 semantic-context boundary:

```bash
python -m pytest -q tests/test_semantic_channels.py tests/test_semantic_binding_propagation.py
```

Набор проверяет immutable context, deterministic catalog version, mapping evidence, stale-context
rejection, compatibility `resolve()` и переход LAS на `context() → resolve_context()`.

Второй ARCH-04 CSV semantic-context slice:

```bash
python -m pytest -q tests/test_semantic_csv_import.py tests/test_semantic_channels.py
```

Набор проверяет CSV/TXT column/header evidence, catalog version provenance и source-contract на
`context() → resolve_context()` без отдельного semantic resolver path.

Третий ARCH-04 Paradox semantic-context slice:

```bash
python -m pytest -q tests/test_paradox_import.py tests/test_semantic_channels.py
```

Набор проверяет Paradox field/mapping evidence, raw-time projection, catalog version provenance
и source-contract на `context() → resolve_context()` без legacy resolver path.

Четвёртый ARCH-04 WITS0 semantic-context slice:

```bash
python -m pytest -q tests/test_wits0_import_review.py tests/test_semantic_channels.py
```

Набор проверяет WITS0 record/item/source-id evidence, automatic/reviewed mapping state,
catalog version provenance и source-contract без legacy `SemanticChannelDictionary.resolve()`.

Пятый ARCH-04 WITSML semantic-context slice:

```bash
python -m pytest -q tests/test_witsml_data_arrays.py tests/test_semantic_channels.py
```

Набор проверяет WITSML channel position/key/uuid evidence, automatic/reviewed/commit mapping state,
catalog version provenance и отсутствие legacy resolver path в общем WITSML Import Review.

Шестой ARCH-04 generic Import Review semantic-context slice:

```bash
python -m pytest -q tests/test_import_review.py tests/test_import_review_controller.py \
  tests/test_semantic_channels.py
```

Набор проверяет read-only inspection, reviewed remapping, сохранение исходного importer evidence
при manual override, catalog version provenance и отсутствие production legacy resolver path.

Седьмой ARCH-04 ETP 1.2 semantic-context slice:

```bash
python -m pytest -q tests/test_etp12_acquisition.py tests/test_etp12_source_contracts.py \
  tests/test_semantic_channels.py
```

Набор проверяет ETP channel URI/id evidence, automatic/reviewed/commit mapping state,
catalog version provenance, сохранение UOM conversion plan и отсутствие legacy semantic resolver.

Финальный ARCH-04 production-wide semantic boundary audit:

```bash
python -m pytest -q tests/test_arch04_semantic_context_boundary.py tests/test_semantic_channels.py
```

AST/source-contract проходит весь `src/geoworkbench`, отслеживает production-объекты
`SemanticChannelDictionary` по типам, factory и присваиваниям и запрещает legacy
`.resolve()` вне compatibility shim. Одноимённые resolver-методы UOM и других сервисов
не считаются нарушением.

ARCH-05 layer import boundary:

```bash
python -m pytest -q tests/test_arch05_layer_import_boundary.py
```

Recursive AST-contract проходит все Python-файлы `src/geoworkbench/domain` и
`src/geoworkbench/calculations`. Проверяются absolute/relative `Import` и `ImportFrom`
в любом AST scope; запрещены PySide/PyQt, PyQtGraph/qtpy, `geoworkbench.ui` и
`geoworkbench.printing`. Таким образом нижние domain/calculation слои остаются headless и
не получают обратную зависимость на UI/printing adapters.

ARCH-06 versioned calculation/conditioning profiles:

```bash
python -m pytest -q tests/test_calculation_profiles.py \
  tests/test_gas_conditioning.py tests/test_gas_ratio_project_controller.py \
  tests/test_project_session_gas_ratios.py tests/test_formula_profiles.py
```

Набор проверяет immutable `GasRatioCalculationProfile`, versioned
`CurveContinuityPolicy`, exact profile resolution, передачу profile UI → controller →
calculations, сохранение profile/policy identity в dataset parameters и неизменность формул/
bounded interpolation в Qt-независимом `calculations` слое.

## 15. Каталоги печатных шапок и логотипов

Минимальная доменная и SKF-проверка:

```bash
python -m pytest -q tests/test_header_catalog.py tests/test_logo_catalog.py \
  tests/test_project_logo_catalog_migration.py tests/test_masterlog_presets.py \
  tests/test_skf_importer.py
```

Полный Windows Release gate дополнительно проверяет Qt-диалоги, A4/A3 portrait/landscape,
многостраничный PDF, SVG/PNG assets и отсутствие регрессий существующих Masterlog/форм.

## 16. Приёмка утверждённого сценария WELL-01…06

Для реализованного паспорта WELL-01:

```powershell
python scripts/run_tests.py -p no:cacheprovider tests/test_well_passport_storage.py tests/test_well_passport_headers.py tests/test_well_passport_dialog.py tests/test_well_passport_pdf.py
```

Набор проверяет валидацию и no-op, отмену, выбор legacy-значений, миграцию конструкции,
раздельность скважин и языков, JSON/пакет/перенос/pending recovery, потерянные assets,
скрытие логотипа, обе A4-ориентации и фактическое содержимое PDF на RU/KK/EN. Отдельные
regressions подтверждают, что паспорт предлагает только catalog-backed customer/contractor
logos, новый uncatalogued raw asset отклоняется controller boundary, а неизменённая legacy
raw-logo ссылка остаётся совместимой при правке других полей. PDF-тест инициализирует
Unicode-шрифты тем же способом, что точка входа приложения.
Ручная проверка: «Файл → Паспорт скважины», заполнить общие поля и переводы, сохранить
диалог и проект (Ctrl+S), открыть повторно и сравнить две ориентации в Центре печати.
Физическую печать этот набор не подменяет.

Матрица принята 5 сентября 2026 года для будущих инкрементов, а не как отчёт о пройденных
проверках. Основа — существующий `tests/test_multilingual_geologpkg_workflow.py`, но он один
не подтверждает готовность всех новых сценариев. Требования WFLOW-001…006 находятся в
[REQUIREMENTS.md](REQUIREMENTS.md); этапы закрываются только в [PROJECT_PLAN.md](PROJECT_PLAN.md).

| Этап | Обязательные сценарии и ожидаемые результаты |
|---|---|
| WELL-01 | Миграция legacy JSON/пакета с несовпадающими реквизитами шапок: сохранить исходные варианты, отмена без записи, подтверждённый общий паспорт. Две скважины не меняют друг друга; save/reopen/backup/recovery/перенос сохраняют ID, числовые данные, все языки, логотипы и конструкцию |
| WELL-02 | Накопительный LAS и только новый суффикс; повтор поставки/no-op; новая кодовая литология/шлам поверх уже заполненных списков; поздний анализ только в выбранные пустоты; correction с явным diff. Проверить оси/единицы, границы, неизвестные коды и конфликт профилей фирмы, ручные overrides и переводы. Ноль сохранён, пропуск источника не очищает проект |
| WELL-02 / запись | Изменение источника после preview, отмена, сбой применения/записи, disk-full, внешняя смена проекта. Нет частичного применения; прежняя дисковая ревизия остаётся читаемой, несохранённое состояние обозначено явно, backup проверен. Рассчитанные кривые помечаются для пересчёта по зависимостям |
| WELL-03 | Переключение вкладок удерживает черновики; Cancel не пишет. Несколько шаблонов добавляют три последовательности блоков; save/reopen сохраняет версии, форматирование и ручные дополнения. Изменение каталога не меняет сохранённые описания; обновление блока не стирает другой язык |
| WELL-04 | Пустой перевод, черновик, подтверждённая и устаревшая версии. Изменение исходного поля затрагивает только зависимые переводы; новая глубина не сбрасывает старые статусы. Fallback не записан как перевод, legacy не объявлен проверенным, список готовности ограничен выбранным диапазоном |
| WELL-05 | A4 portrait/landscape × RU/KK/EN для каждой формы: шапка/лист/планшет одной ориентации и языка, одинаковые числовые данные/границы, длинные подписи и rich text без clipping. Пользовательская пара, универсальная шапка, отсутствующая пара и «без шапки» сохраняют намерение пользователя, реквизиты и правки после открытия проекта |
| WELL-06 | Выбор полного/нового/произвольного диапазона, нескольких форм/языков/ориентаций: все результаты одной сохранённой ревизии. Неполный перевод блокирует итоговую выдачу обязательного поля, явный черновик помечен. Изменения проекта во время выпуска не попадают в snapshot; частичный сбой и повтор не смешивают ревизии и не изменяют старые PDF |

Для удаления блока редактор сохраняет невидимую anchor-границу с его `block_id`. Тест обязан
проверять HTML round-trip, атомарное удаление выбранной вставки из RU/KK/EN, сохранение ручного
текста до/после неё и отказ от удаления старого блока без однозначной границы. Для литологии
дополнительно проверяются независимые черновики вкладок, заполнение RU/KK/EN одним заводским
шаблоном, атомарность controller update при ошибочном языке и отсутствие неявного переноса
legacy/`und` fallback в русский перевод.
Для стратиграфии дополнительно проверяются одновременные название и описание RU/KK/EN,
заполнение всех доступных названий из справочника, сохранение общих глубин/кода/ранга/цвета/
параметров подписи и отсутствие частичной мутации при ошибочном языке.
Быстрый ввод из планшета/Masterlog обязан вернуть те же три языковые версии и один набор чисел.
Для кальциметрии/ЛБА проверяются независимые вкладки описания и заключения, однократный ввод
чисел и классификационных признаков, атомарный отказ при ошибочном языке и защита legacy-fallback.
Для project v31 проверяются миграция v30 без переприсвоения legacy-текста, RU/KK/EN round-trip
на обоих уровнях интерпретации, строгий отказ от неизвестного языка и атомарность controller API.
UI интерпретаций дополнительно проверяет вкладки обоих уровней, единичные числовые поля,
локализованные строки таблицы и отсутствие записи показанного legacy-fallback как перевода.
Для project v32 проверяются round-trip состояния перевода с языком/ревизией источника,
ревизией перевода и зависимостями, отклонение неизвестного языка и миграция v31 в пустой
реестр без ложного состояния `reviewed`.
Доменный workflow WELL-04 проверяется на цепочке draft → reviewed → stale, отказе проверки
при изменённом источнике/зависимости, сохранении номера ревизии и изоляции соседних полей.
Контроллер статусов проверяется на атомарность, content revision/dirty, undo/redo, no-op при
несвязанном изменении и блокировку undo после внешней мутации состояния скважины.
Для project v33 проверяются round-trip ledger ревизий авторских полей, пустая миграция v32,
отказ от отрицательных значений и точечное stale/undo без изменения соседнего интервала.

Данные для автоматизации — синтетические/обезличенные. PDF-приёмка включает проверку текста,
границ страниц и визуальный осмотр RU/KK/EN, а не только создание непустого файла. Физическая
печать и Windows HiDPI проверяются через действующий REL-03, новые функции не считаются готовыми
по одному `compileall`. При чисто документационном утверждении этого решения выполняется
документационный gate из [DOCUMENTATION_POLICY.md](DOCUMENTATION_POLICY.md), без заявления
об успешной runtime-приёмке ещё не реализованных функций.

### WELL-02: read-only план числовых обновлений

```powershell
python scripts/run_tests.py -q -p no:cacheprovider tests/test_well_update_plan.py tests/test_daily_las_growth.py tests/test_daily_las_growth_dialog.py tests/test_proj04_daily_append_rollback.py tests/test_daily_las_growth_autosave.py
python -m benchmarks.benchmark_well_update_plan
```

Проверяются новая глубина, NaN→0, correction с before/after, отсутствие очистки при
NaN источника, восходящая/нисходящая ось, локальные кривые, ограничение diff,
неизменность обоих Dataset, несовместимые единицы/домен/скважина и устаревший fingerprint.
Локальный Windows baseline 6 сентября 2026: 74 профильных теста прошли; synthetic
100k/1M (одна кривая, заполнение пропусков) — 0.423/4.235 s, ratio 10.01 при 10× строк.
В DTO остаётся 200 ячеек diff при полном счётчике. Это замер времени данного сценария,
не RSS gate и не проверка транзакционного применения новых режимов.

Полный локальный Windows-прогон этого инкремента завершился с кодом 0: 2904 passed, 8 skipped; 8 основных shards и 124 native-heavy batches. Полные Ruff, mypy (486 модулей), documentation audit и diff check прошли. Bandit не установлен в окружении; полный release security gate и физическая приёмка REL-03 остаются открытыми.

Повторная проверка WELL-02 покрыта в `test_well_update_plan.py`: полный/сокращённый/пустой
preview, изменение источника, старого участка, локальной кривой, headers, имени/SHA-256
файла и подмена счётчиков/diff. Успех и отказ сохраняют оба Dataset без изменений.

### Применение WELL-02 и история v26

```powershell
python scripts/run_tests.py -q -p no:cacheprovider tests/test_well_update_plan.py tests/test_well_update_apply.py tests/test_well_update_workflow.py tests/test_daily_las_growth_dialog.py tests/test_daily_las_growth_autosave.py tests/test_proj04_daily_append_rollback.py
python -m benchmarks.benchmark_well_update_apply
```

Покрываются явный выбор ячеек, скрытый/подменённый diff, возрастающая/убывающая ось,
NaN и ноль, no-op после повторного анализа, ошибки выделения памяти/регистрации источника,
отмена, external-change, disk-full без ложного успеха, пакетный roundtrip исходных LAS и
истории, миграция v25 → v26 и отказ повреждённой истории. Benchmark 100k/1M проверяет
200 выбранных ячеек и предел временной памяти 240 bytes/row + 8 MiB.

### Геологическое дополнение WELL-02 (v27)

Целевые проверки: `tests/test_well_geology_update.py` и
`tests/test_well_geology_workflow.py`: свободные интервалы, ручные описания и переводы,
коллизии поставщиков, неизвестные коды, разрывы глубины, устаревший план, сохранение
профиля и исходника, откат при ошибке, миграция v26.
Полный прогон и security gate текущего инкремента пока не завершены.


### ARCH-07: общая история редактирования

Первый инкремент проверяет общий chronological stack для Curve Pencil и LAS Header Editor:
cross-domain порядок undo/redo, очистку всей redo-ветки после нового изменения, неизменность
стеков при conflict, listener state для QAction, domain-safe локальный curve undo и глобальную
маршрутизацию MainWindow. Второй инкремент добавляет Curve Metadata update/create/remove:
проверяются shared-history injection, запрет локального undo через более новую команду другого
домена, сохранение существующих conflict guards и global MainWindow routing. Третий инкремент
добавляет Curve Transfer: перенос нескольких кривых является одной командой общего history,
локальные transfer Undo/Redo не перескакивают через более новую команду другого домена, metadata
и values external-change остаются fail-closed, а полностью отменённая Curve Pencil правка не
блокирует последующий Undo переноса из-за одного лишь увеличившегося version counter. Четвёртый
инкремент добавляет Dataset Merge: проверяются два последовательных merge с многошаговым
Undo/Redo, восстановление layout/source sidecars, global MainWindow routing, domain-safe локальные
Merge actions, блокировка при реальном изменении результата и успешный Undo после полностью
отменённой Curve Pencil правки несмотря на увеличившийся curve version. Отдельный disk/export
rollback regression проверяет, что неуспешный merge не остаётся в history и восстанавливает
существовавшую до операции redo-ветку. Пятый инкремент добавляет in-place External LAS Insert:
проверяются shared-history injection, несколько последовательных вставок, domain-safe локальный
Undo, factual metadata/value conflict guard, Undo после полностью отменённой Curve Pencil правки и
global MainWindow routing. Шестой инкремент добавляет Lithology Add/Update/Delete: проверяются
многошаговый chronological Undo/Redo, сохранение identity интервала, translation-tracking
sidecars, domain-safe local undo, fail-closed внешний конфликт и global MainWindow routing.

```powershell
python scripts/run_tests.py -q -p no:cacheprovider tests/test_edit_history.py tests/test_curve_editing_controller.py tests/test_header_editing_controller.py tests/test_curve_metadata_controller.py tests/test_curve_transfer_controller.py tests/test_dataset_merge_controller.py tests/test_external_las_insert_controller.py tests/test_lithology_controller.py tests/test_main_window.py
```


### RPT-QA-01: многостраничные PDF-графики и подписи параметров

Печатный renderer обязан изолировать `QPainter` state между fluid-marker overlay и следующим
листом. Regression воспроизводит ранее наблюдавшийся дефект: полупрозрачная белая marker brush
не должна оставаться активной и превращать финальный `drawRect()` следующей страницы в белую
заливку поверх уже нарисованных кривых. Отдельно проверяется, что legend label берётся из
semantic/Sensors metadata и методики отчёта: source mnemonics вроде `S106`, `S1003`, `S224`
не используются как основной пользовательский заголовок, когда известны «Скорость бур.»,
«Расх. на вых.» и `D-exponent`.

```powershell
python scripts/run_tests.py -q -p no:cacheprovider tests/test_hydrocarbon_interpretation_pdf_chart_range.py tests/test_interpretation_report_charts.py
```


Дополнительный fluid-classification regression сохраняет сырые Haworth/Pixler палетки, но
проверяет report-safe decision layer: конкретный нефтяной подтип разрешается только при
`wetness robust z >= 2.0`, согласованной Pixler oil-band и немixed profile; иначе результат
понижается до вероятных жидких УВ или переходного «жидкие УВ / газоконденсат». Формулировки
и rationale проверяются одновременно на русском, казахском и английском языках.

```powershell
python scripts/run_tests.py -q -p no:cacheprovider tests/test_gas_ratio_interpretation.py tests/test_hydrocarbon_interpretation.py
```


### RPT-QA-01: терминология флюида и читаемые параметры

Видимые отчёты и графики не должны показывать vendor/source mnemonics вроде `S224`,
`S106`, `S1003`, если semantic/Sensors resolver однозначно определяет физический параметр.
Например `S224` в пользовательском выводе становится `D-exponent`. Exact source mnemonic
сохраняется в доменной модели и скрытых audit/source sheets для воспроизводимости.

Fluid labels проверяются на трёх языках как один семантический контракт:
- неопределённый тип: «УВ-флюид неопределённого типа»;
- жидкая тенденция без подтипа: «жидкая УВ-фаза; тип не установлен»;
- согласованная light-oil тенденция: «признаки лёгкой нефтяной фазы»;
- переход light oil / gas condensate: «жидкая УВ-фаза; возможны лёгкая нефть или газоконденсат»;
- газовый класс: «газовая УВ-фаза».

```powershell
python scripts/run_tests.py -q -p no:cacheprovider tests/test_parameter_labels.py tests/test_interpretation_report_charts.py tests/test_hydrocarbon_interpretation.py tests/test_hydrocarbon_fluid_markers.py
```


### RPT-QA-01: OPUS-графики и OPUS Газомер

OPUS использует тот же presentation contract, что и стандартный отчёт. В пользовательских
графиках `OPUS_TG_PCT` отображается как локализованное физическое имя, индикаторы ОПУС
не печатают внутренние мнемоники, а class code 1–7 сохраняется отдельно от локализованной
интерпретации. Маркерные категории должны использовать фазовые формулировки:
нефтяная фаза, газовая УВ-фаза, газоконденсатная УВ-фаза, газированная нефтяная фаза
или УВ-флюид неопределённого типа.

```powershell
python scripts/run_tests.py -q -p no:cacheprovider tests/test_hydrocarbon_fluid_markers.py tests/test_parameter_labels.py tests/test_interpretation_report_charts.py
```


## WITS-ALARM-01 runtime regression

Alarm-domain, persistence/editor and live-runtime checks can be run together with:

```powershell
python -m pytest -q -p no:cacheprovider `
  tests/test_wits0_alarms.py `
  tests/test_wits0_live_forms.py `
  tests/test_wits0_alarm_settings_editor.py `
  tests/test_wits0_live_alarms.py `
  tests/test_acquisition_live_view.py `
  tests/test_wits0_live_view.py `
  tests/test_wits0_operator_dashboard.py
```

The runtime regression specifically guards against debounce advancing on repeated UI refreshes, catches up every DATA_ROW in a drained batch even when the plot is paused/frozen, ignores unrelated record rows, resets pending debounce on an explicit missing channel sample, preserves active alarms through missing input, isolates duplicate canonical mnemonics by curve ID, covers derived-channel catch-up through `source-records` provenance while ignoring unrelated WITS records, and verifies acknowledgement without alarm clearing. It also verifies bounded factual activation/clear history, preservation of CLEAR+ACTIVATE on a direct opposite-side crossing, no fabricated event when a rule is seeded from an existing value, time/depth row-to-axis lookup, one audio cue for a batch containing one or more audio-enabled activations, no replay on an empty/repeated refresh, visual-policy filtering and red activation/green clear threshold markers.

PRINT-STYLE-01 standard grayscale candidate regression in
`tests/test_interpretation_report_charts.py` drives the production band painter with a real
`HydrocarbonCandidateInterval` and asserts three independent cues: filled depth band, fluid
marker geometry, and short text code. The test does not alter classification or source values.

PRINT-STYLE-01 shared-adapter regressions: `tests/test_print_style_shared_adapters.py`
экспортирует geological HTML/PDF/DOCX/XLSX на RU/KK/EN через production entry points.
Изменённый grayscale fixture profile подтверждает shared palette/typography в CSS, OOXML
и workbook styles; PDF проверяется по фактическому тексту. Source curves неизменны.
Qt painter regression проверяет ширину wordmark рядом с номером страницы и restore состояния.
Пункты толщины правил simple tablet header/footer переводятся по DPI устройства;
regression проверяет неизменную физическую толщину при 72/96/144/300/600 DPI.

Geology Office table regression в `tests/test_interpretation_report.py` проверяет все четыре
XLSX table sheets: A4 landscape, physical 100% scale, horizontal pagination, repeat row 1/column A,
минимум 24 pt для wrapped header, shared table font/header fill, alternating body fill,
numeric right alignment и canonical wordmark + &P/&N footer. Существующие проверки продолжают
подтверждать formula-like text safety и исходные типы/значения отчёта.

Document-control slice проверяется `tests/test_report_document_control.py`: 12 production
PDF/DOCX/XLSX комбинаций RU/KK/EN × standard/OPUS × empty/explicit date; authoritative
analysis interval, source-array immutability и неизменный generation audit. Шесть real-workspace
экспортов после package save/reopen подтверждают language selection и отсутствие утечки OPUS
headers в standard. Отдельный тест фиксирует frozen snapshot и formula-like literal cells.

Masterlog document-control: `tests/test_masterlog_document_control.py` проверяет 12 production
PDF/save/reopen сочетаний RU/KK/EN, пустой/явной даты и наличия паспорта скважины,
независимость копии формы и исходной оси. Ещё три GUI regression проверяют доступность
в редакторах данных/динамического поля и очистку даты при принятом паспорте.

Generic document-control: `tests/test_generic_report_control.py` covers 12 RU/KK/EN project
save/reopen HTML/DOCX combinations (bound/unbound form, empty/explicit date), parses every
XML/relationship part, checks footer PAGE/NUMPAGES and repeated table headers, escaped long
text, selected interval and unchanged source arrays. Four guards verify missing/changed form
revisions preserve an existing output; one regression checks compact footer normalization.

Generic control regression matrix now includes real XLSX export after project reopen,
RU/KK/EN sheet names, print-title/footer settings, number types, measured zero, missing
and unavailable channels. Two additional changed/missing-revision guards cover Excel;
three language cases verify formula-like document metadata remains literal text. Existing
interpretation XLSX regressions cover the extracted shared document-control adapter.

`tests/test_masterlog_control_layout.py` adds 18 real PDF export/reopen cases across RU/KK/EN,
A4/A3/roll and empty/explicit date. Each page retains the selected job interval and approvals,
reserves the footer, and preserves physical depth scale including partial final pages. Stored
forms and source arrays remain unchanged. One regression checks multilingual row suppression
and legacy inactivity; ten narrow/wide long-text cases at 72/96/144/300/600 DPI verify all
automatic text rectangles stay outside the graph body.

`tests/test_interpretation_control_footer.py` covers 24 production PDF exports after package
save/reopen: RU/KK/EN × standard/OPUS × empty/explicit date × portrait/landscape. Every
page retains document/revision/status/confidentiality and localized numbering; saved
composition, depth and curve arrays are unchanged. Ten narrow/wide QPdfWriter cases at
72/96/144/300/600 DPI verify footer bounds and extracted physical font size. One regression
checks that empty footer metadata retains legacy content geometry even with an explicit date.

Six production overflow regressions in `tests/test_interpretation_report_charts.py` replace
an old source-string suppression check. RU/KK/EN × FULL/HIDE verify a 120-rock catalog:
methodology precedes charts, full legends follow charts with every code/name preserved,
and HIDE suppresses the catalog. The existing Windows method/geology ordering regression
is retained unchanged.

`tests/test_report_document_control_docx_footer.py` adds 24 polished Word export/reopen
cases: RU/KK/EN × standard/OPUS × empty/explicit date × short/long XML-sensitive metadata.
Every XML/relationship part is parsed; footer content type and relationships, both section
references, margin reservation, percentage widths, exact row heights, PAGE/NUMPAGES and
font size are checked. Full metadata remains in the cover; footer details are bounded and
exclude date/audit values. Composition, depth and curve arrays are unchanged. Six ordinary
exports cover localized shared brand/numbering; one injected rewrite failure preserves an
existing output and removes staging files. Generic Office regressions cover the shared adapter.
Word pagination and physical printer acceptance remain separate checks.

Windows WITS operator-dashboard tests use the existing fresh-process-per-test policy
in `scripts/run_tests.py` after an observed 0xC0000005 in a large offscreen Qt shard.
`test_windows_qt_test_isolation.py` verifies that every dashboard node is scheduled exactly
once, outside the regular shard, in its own batch. All dashboard assertions remain intact.

Masterlog visual-profile regressions (`test_masterlog_header_visual_profile.py`) substitute
colour/grayscale profiles and typography/rule metrics, verify real QPainter output and
explicit form overrides, then save/reopen and export A4/A3/roll PDF in RU/KK/EN. Vector PDF
fills/borders and reusable header backgrounds must follow the injected profile; source
curve arrays and the saved template remain unchanged. Physical print acceptance remains open.

`test_masterlog_curve_legend.py` compares legend and plotted QPen colour/width/style for
all four saved line styles, checks point predicate identifier parity, vendor-bound units,
missing channels and narrow positive label rectangles. RU/KK/EN × A4/A3/roll project reopen
exports inspect PDF dash geometry and real black-on-white QPainter output; persisted
column properties and source arrays remain unchanged. Physical acceptance remains open.

Masterlog grid/profile regressions check colour/grayscale roles, saved alpha 0/0.6/1,
major/minor physical weight and five-metre coordinate invariants. RU/KK/EN reopen exports
at injected PDF writer DPI 72/300/600 verify vector border weights and depth font role,
with source arrays and templates unchanged. The production export DPI setting stays 300.

Gas-context print-track regressions (`tests/test_gas_context_print_track.py`) cover all 13 event
type codes and RU/KK/EN labels, existing registry priority for overlaps/repeats/point events,
draft/hard-exclusion visibility, neutral/grayscale border styles and exact-depth tiny bands.
Project save/reopen drives standard/enhanced PDF plus PNG preview and asserts registry/candidate
and source-array immutability. Isolated real-PDF context painters verify 6 pt codes at
72/300/600 DPI; the production interpretation PDF path uses 72 DPI. A 100-event legend with
long IDs verifies wrapping, pagination, complete text and page bounds. Physical printer and
live/tablet alarm acceptance remain open.

`tests/test_gas_context_report_identities.py` checks every InterpretationImpact and real standard/OPUS save/reopen followed
by HTML, PDF, standard/polished DOCX and XLSX export in RU/KK/EN. Repeated events keep distinct
IDs, hidden draft/hard-excluded events stay absent, XML/HTML-sensitive and formula-like IDs
remain text, and depth/TG/QC cells remain numeric. PDF assertions allow natural line wrapping;
source arrays, registry, candidates and suppressed audit evidence remain unchanged.

Existing gas-context print-track regressions retain all 13 event-code/type labels in RU/KK/EN.

## Signed-depth gas-context acceptance

`tests/test_gas_context_negative_depth_acceptance.py` проверяет отрицательные MD/TVD/TVDSS
через transactional editor, JSON/package save/reopen, выбранный standard/OPUS interval
и реальные HTML/PDF, обычный/оформленный Word, Excel на RU/KK/EN. Проверяются event ID,
границы, measured TG/manual QC/delta, числовые ячейки и неизменность источников/audit.
Отдельно проверяются UI TVDSS без clamping, отказ add/update при NaN/inf/обратных границах,
analysis range validation, time-axis rejection и неприменение чужой/неоднозначной legacy оси.
Well-wide события могут выходить за диапазон одного dataset; ограничение относится к
выбранному analysis interval. Этот автоматический gate не заменяет физическую/полевую приёмку.

## Geology-legend visual-profile regression

`tests/test_geology_legend_visual_profile.py` checks colour/grayscale semantic profile substitution,
unchanged lithology patterns and LBA intensity colours, real full/compact RU/KK/EN PDF text at
72/300/600 DPI (physical caption/table point sizes and border weights), and production
standard/OPUS PDF plus PNG after project reopen. Source arrays and geology snapshots remain
unchanged. Existing legend/readability tests cover complete code decoding, long labels,
explicit ellipsis and large-catalog pagination; physical printer acceptance remains external.

`tests/test_interpretation_chart_visual_profile.py` checks 24 real multipage PDF cases: standard/enhanced, RU/KK/EN, A4 portrait/landscape and colour/grayscale profiles. Distinct substituted palette roles must appear in actual fills, strokes and text; source curve colours, arrays and metadata remain unchanged.

`tests/test_interpretation_heading_rule_profile.py` covers invalid physical font sizes, unchanged pixel-preview fonts, real wrapped RU/KK/EN headings at 72/300/600 DPI and actual standard/enhanced multipage A4 portrait/landscape PDFs under custom typography/rule profiles. It checks full heading text, reserved bounds, physical point sizes/line widths and unchanged source arrays; remaining non-heading chart typography and physical printer acceptance are separate scopes.

`tests/test_interpretation_text_physical_dpi.py` checks 42 actual PDFs: standard/enhanced RU/KK/EN charts at 72/300/600 DPI in A4 portrait/landscape, including signed depths and substituted integer table/caption sizes, plus real candidate codes at each DPI. Extracted title, axis, legend and marker sizes must retain their physical 72-DPI baseline; source arrays/metadata and candidate identity remain unchanged.

Interpretation source curves and ratio-reference traces use non-cosmetic physical-point pens (1.25/0.7 pt); real PDF stroke-width/dash regressions at 72/300/600 DPI prevent high-resolution washout while retaining source values, colours and geometry.

Ratio-scale readability: `tests/test_ratio_scale_heading.py` проверяет реальные PDF 72/300/600 DPI, 22/40/90 pt lanes, linear/log scales, полные bounded endpoint labels без пересечения, caption profile substitution и production RU/KK/EN A4 portrait/landscape. Source arrays/metadata и continuous dashed ratio traces сохраняются.

`tests/test_interpretation_note_caption_profile.py` проверяет полный explanatory note над footer и ниже source traces в actual standard/OPUS PDF: caption profile 9 pt, RU/KK/EN, A4 portrait/landscape, 72/300/600 DPI. Отдельно проверяются полные localized no-data captions forced-empty cuttings/LBA. Source arrays/metadata сохраняются.

`tests/test_fluid_marker_legend_caption_layout.py` проверяет полный текст всех пяти фаз и пояснения, реальные font sizes, bounded/non-overlapping spans и glyph colours на RU/KK/EN, 72/300/600 DPI, 180/360/550 pt widths и default/9 pt caption profiles. Все non-empty phase subsets помещаются в global budget. Production многолистовые A4 portrait/landscape PDF сохраняют footer bounds, source arrays/metadata и candidate identities; invalid widths отклоняются.

Fluid marker legend использует QTextLayout для определения строк и явный point-metrics line pitch для измерения/рисования: Windows font bounding boxes не пересекаются при малом caption size. Строгие PDF span checks сохраняются. Planner-only report fixtures содержат пустой candidates contract.

`tests/test_curve_legend_caption_layout.py` covers 54 real PDF legend layouts (RU/KK/EN, 72/300/600 DPI, 100/180/300 pt widths, default/9 pt captions) and 36 production standard/OPUS A4 portrait/landscape PDFs. It checks full labels/units/scientific ranges, bounded non-overlapping spans, physical font size, first-line glyph alignment, measured reserve above notes, and unchanged source arrays/metadata. Additional regressions reject invalid widths, preserve missing-range colour indices, retain supplementary Unicode across Qt UTF-16 line breaks, and remeasure changed page-local ranges after replanning. Existing physical-DPI tests now assert shared caption size for curve legends.

`tests/test_interpretation_cover_physical_dpi.py` checks 24 cover contracts across actual 72/300/600 DPI PDFs: RU/KK/EN, standard/OPUS, A4 portrait/landscape and absent/explicit dates. Full localized titles/subtitles, document-control values, approvals and notes must survive with matching extracted physical font sizes and text bounds relative to 72 DPI. Six QPrinter PDF cases exercise the real paged printer adapter at 600 DPI; six production multipage renderer cases preserve the selected interval, manual identity, source arrays/metadata and absence of generation timestamps. This does not substitute for physical-printer acceptance.

Windows quality gate also isolates all four `test_navigation_organization.py` MainWindow scenarios into single-test processes after an observed 0xC0000005 in pyqtgraph PlotItem construction following earlier dialogs/scenes in a long shared Qt shard. Runner regressions verify every selector is preserved exactly once and excluded from regular shards; assertion/native failures still fail the gate.

`tests/test_interpretation_narrative_point_layout.py` checks 36 actual rich-text PDFs:
RU/KK/EN, 72/300/600 DPI, default/custom typography and regular/compact table cells.
Extracted physical fonts and full text must fit the measured document bounds; source
class selectors cannot defeat compact fallback. Twelve multipage QPdfWriter/QPrinter
PDF cases retain each of 120 rows exactly once, repeat headers and stay above footers
in A4 portrait/landscape at 600 DPI. A character-format regression preserves heading
links/bold/italic and body superscript/subscript. Physical printer acceptance is separate.

`tests/test_interpretation_cover_typography_profile.py` checks 36 actual covers:
RU/KK/EN, 72/300/600 DPI, A4 portrait/landscape, default/custom title/subtitle/body/caption
roles. Full control/context/approval labels and values, localized multiline title/subtitle,
notes and signature captions must survive; physical font sizes, page bounds and pairwise
span intersections are checked without weakening clipping assertions. Source report/identity
remain unchanged. Existing QPrinter cover checks now expect the shared 22-pt title in both
orientations; full production/high-DPI contracts remain in place.

Cover wrapped text uses QTextLayout for line breaks and explicit point-metrics pitch
for both measurement and drawing. This fixes Windows default/custom font bounding-box
overlap without relaxing the PDF intersection tolerance. Variable context row/pair heights
reserve complete labels/values before drawing. Five additional regressions reject invalid
widths and preserve explicit paragraph breaks plus supplementary Unicode via UTF-16 offsets.

`tests/test_gas_mixture_report_visual_profile.py` checks 36 production PDFs:
RU/KK/EN, 72/300/600 DPI, chart/text modes and default/substituted palette/typography.
Actual title/section/table point sizes, text colours, table header fills, full component
and Pixler numerical rows, page bounds, canonical brand and absent audit timestamp are
required. Full warnings are checked across page breaks after verifying and removing only
the separate lower-right Qt page-number block. A cross-page regression retains numeric
content inside the warning; all PDF spans, including page numbers, still undergo bounds checks.
Dataset arrays/metadata and immutable report audit remain unchanged. Six PNG
cases retain all five continuous component lines/colours and measure neutral text/page,
antialiased grid and frame palette blends at known positions. Forced font-adapter/print failures
preserve an existing PDF and remove temporary output after closing the writer. Existing interpretation rich-text
regressions verify the shared adapter extraction preserves inline formatting and pagination.

Windows depth-refresh MainWindow tests run individually through the existing native-process
isolation policy after a shared-shard PlotItem access violation during depth reset. Runner
contract tests require both nodes exactly once, retain all assertions and reject failed exits.

Masterlog document-control text explicitly resolves the common Unicode print-family stack,
independently of the UI default font. Regular/bold font regressions and RU/KK/EN production
PDFs after a UI-font change require complete document numbers, approvals, date and interval.
