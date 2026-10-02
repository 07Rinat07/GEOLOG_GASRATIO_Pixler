# Производительность

Этот документ фиксирует воспроизводимые performance-контракты для ресурсоёмких production paths.
Контракт `GAS-08` относится к кондиционированию C1-C5 и производным Gas Ratio/Pixler/Haworth;
контракт `PERF-03` — к длительному acquisition append. Математические формулы расчёта здесь не
дублируются и не изменяются.

## WITS-MEM-01 — память временного WITS preview

`python -m benchmarks.benchmark_wits_preview --buffer-frames 100` запускает два независимых
процесса с одинаковым WITS-профилем: 100 и 1000 кадров с постоянной схемой. JSON сохраняет
baseline/current sampled peak/lifetime peak RSS, время, число вытесненных кадров, compaction,
строки Dataset и записи сессии. Порог прироста sampled RSS после инициализации между 1× и 10×
— 96 MiB; это консервативный запас для разных Windows runner и allocator, а не допустимый размер
самого preview. Строки и записи остаются в пределах 1×–2× окна после его заполнения: gate также
отклоняет потерю удерживаемых измерений. При смене профиля, Python или платформы сравнивать
измерения в одинаковой среде; lifetime peak RSS приводится для диагностики отдельно от gate.
Измерение текущего RSS после каждого кадра не учитывает кратковременные выделения внутри observe;
они ограничиваются отдельными bounded-структурами и числом записей. Эта synthetic
проверка не заменяет длительный прогон реального обезличенного raw-потока и полевую приёмку.

## WELL-02 — проверка состояния перед daily LAS append

Для transient fingerprint ежедневного LAS (WELL-02) отдельная команда
`python -m benchmarks.benchmark_daily_las_preview` измеряет 100k/1M строк, семь кривых и
пять повторений. Сложность O(число отсчётов + metadata), массивы читаются блоками до
131 072 элементов; план сохраняет только два digest. Временные выделения fingerprint по
`tracemalloc` ограничены 4 MiB для benchmark с фиксированным объёмом metadata; это не RSS
процесса и не время полного append. Локальный Windows/Python 3.11.9 замер 6 сентября 2026:
100k — 4,56 мс / 801 170 B; 1M — 61,38 мс / 1 049 698 B. Существующие audit hashes остаются
побайтно совместимыми, включая strided/descending/datetime массивы.

## GAS-08 — кондиционирование и Gas Ratio

### Что измеряется

Канонический runner: `benchmarks/benchmark_gas_conditioning.py`.

По умолчанию он выполняет два сценария с одной и той же детерминированной формой данных:

- `100 000` строк;
- `1 000 000` строк;
- 7 исходных каналов: `C1`, `C2`, `C3`, `IC4`, `NC4`, `IC5`, `NC5`;
- редкая штатная дискретизация с двумя `NaN` между измеренными строками;
- один длинный пропуск, который должен оставаться разрывом после conditioning;
- не менее 3 повторений каждого размера.

Измеряются:

- best wall time;
- median wall time — основной стабильный показатель времени;
- throughput в строках/с по median;
- process-level peak RSS в MiB;
- число интерполированных строк;
- число производных кривых;
- масштабирование времени и RSS между 100k и 1M.

Исходные массивы дополнительно проверяются по SHA-256 до и после расчёта. Benchmark считается
некорректным, если production pipeline изменил входные `depth` или gas arrays in-place.

### Почему каждый размер запускается отдельно

Peak RSS — lifetime maximum процесса. Если 100k и 1M измерять последовательно в одном процессе,
первый сценарий может загрязнить результат второго. Поэтому основной runner создаёт отдельный
worker-процесс для каждого размера. Время фиксируется только вокруг
`calculate_conditioned_ratios(...)`, а RSS снимается средствами ОС и учитывает native memory
NumPy/SciPy, которую `tracemalloc` не видит полностью.

На Windows используется `GetProcessMemoryInfo(...).PeakWorkingSetSize`; на POSIX —
`resource.getrusage(...).ru_maxrss` с нормализацией единиц.

### Release-gate

Pull request и push в `main` выполняют benchmark через `.github/workflows/release-gate.yml`.
Полный JSON сохраняется в artifact качества как:

`build/ci-artifacts/quality/gas-conditioning-benchmark.txt`

Команда для локального повторения:

```powershell
python benchmarks/benchmark_gas_conditioning.py --json
```

Для исследовательского запуска без блокировки по guardrails:

```powershell
python benchmarks/benchmark_gas_conditioning.py --json --no-enforce
```

`--no-enforce` допустим только для локального профилирования. Release-gate всегда запускает
обычный enforcing mode.

### Начальные guardrails

Первый hardware-independent gate использует широкие абсолютные пределы и отдельную проверку
масштабирования. Они предназначены для обнаружения material regression, а не для сравнения
скорости разных компьютеров.

| Набор | Median wall time, max | Peak RSS, max |
| --- | ---: | ---: |
| 100 000 строк | 5.0 s | 512 MiB |
| 1 000 000 строк | 45.0 s | 1536 MiB |

Дополнительно при переходе от меньшего набора к большему:

- time ratio не должен превышать `size_ratio × 2.0`;
- RSS ratio не должен превышать `size_ratio × 1.5`.

Для канонических 100k → 1M это означает явный запрет на очевидно сверхлинейное поведение без
изменения production-формул.

### Принятый Windows baseline

Первой принятой точкой является Windows release-gate run `#844` для commit
`8f3bb773423ea30a273bf77994a62850118bffe9` от 2 сентября 2026 года. Gate завершился успешно,
а исходный JSON сохранён в artifact `release-quality-33600135051`.

| Набор | Median wall time | Best wall time | Throughput | Peak RSS |
| --- | ---: | ---: | ---: | ---: |
| 100 000 строк | 3.080 s | 3.010 s | 32 466 rows/s | 155.2 MiB |
| 1 000 000 строк | 30.248 s | 29.974 s | 33 061 rows/s | 1230.2 MiB |

Масштабирование 100k → 1M при увеличении объёма в `10.0×` составило `9.82×` по median wall time
и `7.93×` по peak RSS. Оба результата находятся внутри начальных абсолютных и scaling guardrails.
Для сравнения последующих изменений используется полный JSON artifact, а округлённые значения в
таблице служат читаемой зафиксированной reference point.

### Правило изменения baseline GAS-08

Принятый Windows release-gate JSON является исходной наблюдаемой точкой для дальнейших
сравнений. Любое последующее изменение benchmark fixture, сценария, числа повторений или
guardrails должно обновляться в одном PR вместе с этим документом и `PROJECT_PLAN.md`.

Следующие изменения требуют отдельного объяснения и проверки, если относительно принятой точки:

- median wall time увеличился более чем на 20%;
- peak RSS увеличился более чем на 30%;
- рост 100k → 1M стал явно хуже линейного;
- число повторений стало меньше 3;
- в один результат начали смешиваться разные data-shape сценарии.

Absolute guardrails можно только ослаблять с явным техническим обоснованием в PR. Улучшения
производительности допускают ratchet вниз после нескольких повторяемых Windows CI прогонов.

## PERF-03 — длительный acquisition append

Канонический runner: `benchmarks/benchmark_acquisition.py`. Он создаёт детерминированную GTI
session с depth index, Total Gas и ROP и прогоняет `50 000`, `100 000` и `1 000 000` записей.
Каждый размер выполняется в отдельном worker-процессе, поэтому peak RSS одного сценария не
загрязняется предыдущим.

Измеряемый production hot path — только `AcquisitionController.enqueue_many()` и
`AcquisitionController.drain()` с `batch_size=64`. Конструирование входных `AcquisitionRecord`
в таймер не входит. Apply-results удерживаются только на время текущего batch; append-only journal
session при этом естественно растёт до полного размера и участвует в long-session проверке.

Latency p95 рассчитывается nearest-rank методом только по полным batch64. Сравнение начала и конца
session использует одинаковые batch-aligned окна по `157 × 64 = 10 048` строк; это намеренно
чуть больше номинальных 10k, чтобы partial tail не улучшал последнюю метрику искусственно.
Peak RSS фиксируется как наблюдаемая диагностическая метрика, но PERF-03 не задаёт для него
отдельный release threshold.

### Enforcing guardrails PERF-03

Release gate считается неуспешным при любом из условий:

- для доступной пары `N → 2N`: `T(2N) / T(N) > 2.5`;
- p95 полного batch64 `> 50 ms`;
- отношение суммарного времени последнего/первого batch-aligned окна `> 2.0`;
- benchmark фактически использовал batch size, отличный от 64.

По умолчанию матрица содержит 50k/100k/1M, поэтому прямой doubled-size guard применяется к
50k → 100k. 1M дополнительно покрывает длительную session, p95, last/first и наблюдаемую память.

Quality artifact:

`build/ci-artifacts/quality/acquisition-benchmark.txt`

Команды:

```powershell
python benchmarks/benchmark_acquisition.py --json
python benchmarks/benchmark_acquisition.py --json --no-enforce
```

`--no-enforce` предназначен только для локального исследования; Windows release gate использует
enforcing mode.

### Принятый Windows baseline PERF-03

Первой принятой точкой является Release gate `#886` для code head
`112d4bb488515c06aaaa0580ebf51636a35c7136` от 2 сентября 2026 года. Все quality, security и
GUI/HiDPI/PDF jobs завершились успешно; исходный JSON сохранён в artifact
`release-quality-33661028295`.

| Набор | Timed total | Throughput | p95 batch64 | First window | Last window | Last/first | Peak RSS |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| 50 000 | 3.504 s | 14 267 rows/s | 4.684 ms | 699.652 ms | 711.888 ms | 1.017 | 69.6 MiB |
| 100 000 | 7.027 s | 14 231 rows/s | 4.663 ms | 688.363 ms | 694.121 ms | 1.008 | 107.9 MiB |
| 1 000 000 | 70.605 s | 14 163 rows/s | 4.640 ms | 691.953 ms | 683.928 ms | 0.988 | 784.5 MiB |

Для 50k → 100k `T(2N)/T(N)=2.005`, то есть меньше лимита `2.5`. Максимальный наблюдённый p95
составил `4.684 ms` против лимита `50 ms`, а максимальный last/first — `1.017` против `2.0`.
В baseline JSON список `violations` пуст.

### Правило изменения baseline PERF-03

Изменение fixture, timed region, batch size, percentile method, размера first/last window или
любого enforcing guardrail выполняется только вместе с обновлением этого документа и
`PROJECT_PLAN.md`. Ослабление guardrail требует явного технического обоснования; локальный
`--no-enforce` не является доказательством прохождения release criteria. Peak RSS может получить
отдельный enforcing budget только отдельным плановым инкрементом, а не задним числом внутри
PERF-03.

## PERF-04 — revision-based tablet geometry cache

`CurveGeometryCache` сохраняет sampled viewport geometry по ключу, включающему curve/axis id,
`values_revision`, `axis_revision`, границы viewport, LOD budget и continuity-specific признаки.
Кэш ограничен одновременно числом записей и hard budget `64 MiB` для NumPy payload. В byte
accounting входят `nbytes` двух принадлежащих кэшу массивов (`values` и vertical axis); Python
object/key/`OrderedDict` overhead остаётся ограничен отдельным `max_entries`.

Cold miss и zoom miss выполняют production `select_visible_samples(...)`/gas-specific sampler и
имеют сложность `O(N)` по рассматриваемому исходному массиву. Cache hit выполняется через
`OrderedDict` lookup/move-to-end и имеет ожидаемую сложность `O(1)`. При превышении бюджета
удаляются LRU entries до одновременного соблюдения `max_entries` и `max_bytes`; единичная geometry,
которая сама превышает budget, возвращается renderer'у, но не удерживается в кэше.

### Benchmark и release contract PERF-04

Канонический runner: `benchmarks/benchmark_curve_sampling.py`. Каждый размер выполняется в
отдельном worker-процессе, чтобы lifetime peak RSS предыдущего сценария не загрязнял следующий.
По умолчанию проверяются `1 000 000`, `5 000 000` и `10 000 000` source samples с
`max_points=4096` и три последовательных операции:

1. **cold** — full-viewport miss, sampling + cache insert;
2. **hit** — повторный запрос того же revision/viewport key;
3. **zoom** — новый viewport key, требующий повторного sampling.

Runner проверяет структурный контракт: ровно один hit и два miss, обе cold/zoom geometry остаются
в кэше, `current_bytes <= max_bytes`, sampled geometry не пуста, peak RSS доступен. Первый baseline
намеренно не вводит hardware-dependent timing threshold; timings и RSS являются принятой reference
point, а bounded-memory invariants уже являются enforcing criteria. Любой будущий timing guardrail
добавляется отдельным обоснованным ratchet после повторяемых Windows CI прогонов.

Quality artifact:

`build/ci-artifacts/quality/curve-sampling-benchmark.txt`

Команда:

```powershell
python benchmarks/benchmark_curve_sampling.py --json
```

### Принятый Windows baseline PERF-04

Первой принятой точкой является Release gate `#894` для code head
`ac6c60d7f50825bd59a6c5ada5a0595e06fa3bb2` от 2 сентября 2026 года. Quality, security и
GUI/HiDPI/PDF jobs завершились успешно; исходный JSON сохранён в artifact
`release-quality-33668589275`.

| Source samples | Cold | Hit | Zoom | Cached payload | Peak RSS |
| ---: | ---: | ---: | ---: | ---: | ---: |
| 1 000 000 | 43.049 ms | 0.0038 ms | 27.797 ms | 128 KiB | 84.5 MiB |
| 5 000 000 | 161.581 ms | 0.0036 ms | 106.746 ms | 128 KiB | 302.1 MiB |
| 10 000 000 | 289.547 ms | 0.0034 ms | 197.813 ms | 128 KiB | 574.2 MiB |

Во всех трёх worker-процессах cold и zoom сохранили по `4096` output rows, кэш содержал ровно две
geometry без eviction: `131 072 B` при hard budget `67 108 864 B`. Это фиксирует, что cache
residency зависит от bounded rendered geometry, а не от 1/5/10M source length. Peak RSS включает
исходные benchmark arrays и поэтому ожидаемо растёт с размером fixture; он не является размером
самого geometry cache.


## PERF-07 — LAS → первый TabletView render → scroll/zoom

PERF-07 закрывает промежуток между существующими импортными метриками
`las.import.performance`/`las.import.presentation` и низкоуровневым PERF-04. Канонический runner:
`benchmarks/benchmark_las_tablet_pipeline.py`.

Runner создаёт временный deterministic LAS, близкий по форме к рабочему Maksat M-1:
`27 500` строк, `351` data curve и `16` видимых curve-track. Файл создаётся streaming-записью
до timed region и не коммитится в репозиторий. В одном изолированном worker-процессе измеряются:

1. production `import_las_with_report()` целиком;
2. первый `TabletView.set_layout_and_dataset()` + обработка Qt events;
3. реальный `scroll_depth()`;
4. реальный `zoom_depth()`;
5. current/peak RSS checkpoints до импорта, после импорта, первого render и navigation.

Сам `TabletView.refresh_view()` дополнительно сохраняет duration/RSS в существующем
`tablet.render.full.finished`, поэтому field diagnostics и synthetic benchmark используют одну
production boundary без второго renderer.

Первый PERF-07 gate намеренно **не** задаёт wall-clock/RSS threshold: baseline зависит от Windows
runner, Qt и стоимости lasio parse. Enforcing criteria на этом этапе структурные:

- число импортированных строк/кривых совпадает с fixture;
- первый presentation вызывает ровно один `DirtyRenderStats.full_updates`;
- scroll и zoom реально меняют viewport;
- scroll/zoom не увеличивают `full_updates`;
- первый render проходит production geometry cache для всех выбранных curve-track;
- RSS, если платформа его предоставляет, должен быть положительным.

Quality artifact:

`build/ci-artifacts/quality/las-tablet-pipeline-benchmark.txt`

Команды:

```powershell
python benchmarks/benchmark_las_tablet_pipeline.py --json
python benchmarks/benchmark_las_tablet_pipeline.py --rows 1000 --curves 8 --render-tracks 4 --json
```

Вторая команда предназначена только для быстрой локальной диагностики.

### Принятый Windows baseline PERF-07

Первой принятой точкой является Release gate **#2297** для PR #423, final head
`514a6be7cd1ae09cc064dcebe0db796ff13a0d05` от 2 октября 2026 года. Quality, security и
GUI/HiDPI/PDF jobs завершились успешно.

| Этап | Время |
| --- | ---: |
| LAS import total | 12 484.34 ms |
| Первый render 16 curve-track | 629.01 ms |
| Scroll | 60.29 ms |
| Zoom | 109.67 ms |

RSS вырос примерно с 102.0 MiB до 323.5 MiB после import, 372.9 MiB после первого render и
392.7 MiB после navigation. Lifetime peak процесса составил около 1284.0 MiB. Structural contract
также подтверждён: initial presentation дал ровно один full rebuild, scroll/zoom — ноль;
geometry-cache misses выросли 16 → 48 без скрытого rebuild.

Import занимает более 90% измеренного wall-clock pipeline и поэтому является следующим
подтверждённым hot path. Release gate **#2299** разложил import: source `809.28 ms`, lasio parse
`5 957.19 ms`, Dataset materialization `14 263.00 ms`, report `44.68 ms`; total
`21 074.15 ms`. Materialization — крупнейшая подтверждённая фаза.

Следующий PERF-07 slice не меняет parser/storage/semantic contracts. Production event
`las.import.performance` дополнительно разбивает `dataset_ms` на `dataset_setup_ms`,
`dataset_curve_values_ms`, `dataset_curve_canonical_ms`, `dataset_curve_semantic_ms`,
`dataset_curve_store_ms` и `dataset_headers_ms`. End-to-end benchmark переносит эти поля в
Windows JSON. После принятого run оптимизируется только фактически доминирующая materialization
подфаза.

Release gate **#2301** подтвердил подфазу: `dataset_curve_values_ms = 13 889.20 ms` из
`dataset_ms = 14 094.48 ms`; canonical inference занял 91.81 ms, semantic resolution 49.26 ms,
CurveData/store 10.70 ms, setup 22.71 ms. Полевой diagnostics bundle от 2 октября 2026 года
(`well Maksat#M1 from to 5680m`, 28 146 строк, 342 кривые, 66.36 MB) независимо подтвердил тот
же профиль: total import 24.84 s, Dataset materialization 18.73 s, lasio parse 5.43 s, первый
9-track render 0.626 s.

Причина `curve_values` — повторное чтение computed `LASFile.data` внутри цикла по каждой
кривой. Текущий slice материализует positional row×curve matrix один раз на импорт, после чего
копирует только нужные столбцы. Это сохраняет duplicate-mnemonic semantics и fallback по mnemonic
для источников без валидной positional matrix. Regression test фиксирует ровно одно обращение к
`LASFile.data`.

Post-merge Release gate **#2304** на `main` подтвердил результат PR #426 на той же synthetic
M-1 форме: logged import `6 144.72 ms` (wall `6 151.42 ms`), source `756.39 ms`,
lasio parse `5 161.15 ms`, Dataset materialization `184.46 ms`, report `42.73 ms`.
Внутри Dataset теперь curve-values занимают только `58.91 ms`; прежний bottleneck
`14 094.48 ms` materialization устранён примерно на два порядка, а крупнейшей подтверждённой
фазой стал parser. Первый 16-track render в этом run занял `1 460.39 ms`, scroll
`118.19 ms`, zoom `210.00 ms`; structural full-rebuild contract остался зелёным.

Release gate **#2347** на exact head PR #428 подтвердил следующий bottleneck:
`parse_ms = 4 636.005 ms`, из них `parse_lasio_ms = 4 635.229 ms`,
`parse_stream_setup_ms = 0.022 ms`, `parse_index_ms = 0.490 ms`. Dataset materialization
осталась `195.835 ms`; первый 16-track render — `1 419.731 ms`. Следовательно почти всё
оставшееся parse-время находится внутри data/header reader lasio, а не в stream wrapper или
извлечении index.

Текущий оптимизационный slice сохраняет lasio владельцем header parsing и вводит только
fail-closed numeric fast path для обычного LAS 1.2/2.x: одна ASCII-секция, `WRAP=NO`,
whitespace delimiter и точное совпадение числа parsed columns с объявленными curves.
Data matrix читается через `numpy.loadtxt`, NULL заменяется только в non-index columns,
после чего данные присваиваются lasio CurveItem по позиции. Любая неподдерживаемая версия,
wrapped/comma layout, shape mismatch или numeric parse error автоматически повторно открывает
исходные неизменённые bytes через прежний полный `lasio.read`. PERF-07 synthetic fixture
обязан использовать fast backend; compatibility fixtures отдельно фиксируют fallback.

## Границы ответственности

Benchmarks не заменяют correctness-тесты и не дублируют production-алгоритмы. GAS runner отвечает
за fixture, измерение и immutable-input checks вокруг расчётного pipeline. Acquisition runner
отвечает за детерминированную нагрузку, измерение production controller и enforcement
performance-контракта; источником истины для append/replay остаётся application service.
Tablet PERF-04 runner отвечает за cold/hit/zoom измерение production geometry-cache seam,
структурный byte-budget contract и OS-level peak RSS; sampling semantics остаются в production
`geoworkbench.tablet` модулях.
