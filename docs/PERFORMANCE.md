# Производительность расчётов бурового газа

Этот документ фиксирует воспроизводимый performance-контракт для кондиционирования C1-C5 и
производных Gas Ratio/Pixler/Haworth кривых. Он относится к задаче `GAS-08` из
[PROJECT_PLAN.md](PROJECT_PLAN.md) и не меняет математические формулы расчёта.

## Что измеряется

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

## Почему каждый размер запускается отдельно

Peak RSS — lifetime maximum процесса. Если 100k и 1M измерять последовательно в одном процессе,
первый сценарий может загрязнить результат второго. Поэтому основной runner создаёт отдельный
worker-процесс для каждого размера. Время фиксируется только вокруг
`calculate_conditioned_ratios(...)`, а RSS снимается средствами ОС и учитывает native memory
NumPy/SciPy, которую `tracemalloc` не видит полностью.

На Windows используется `GetProcessMemoryInfo(...).PeakWorkingSetSize`; на POSIX —
`resource.getrusage(...).ru_maxrss` с нормализацией единиц.

## Release-gate

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

## Начальные guardrails

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

## Принятый Windows baseline

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

## Правило изменения baseline

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

## Границы ответственности

Benchmark не является заменой correctness-тестам. Он не меняет и не дублирует алгоритмы из
`src/geoworkbench/calculations/`; расчётные функции остаются единственным production source of
truth. Performance runner отвечает только за fixture, измерение, проверку immutable inputs и
регрессионный gate.
