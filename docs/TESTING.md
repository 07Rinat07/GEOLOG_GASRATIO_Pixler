# Проверка качества и release gate

Документ актуален для **GEOLOG GASRATIO@Pixler 0.7.93** на 2 августа 2026 года. История
продуктовых изменений находится в `CHANGELOG.md`; CI artifacts не заменяют текущие команды,
ручную проверку и regression fixtures.

## 1. Принципы тестирования

1. Проверяется контракт, а не конкретная реализация. Тест меняется только при намеренном
   изменении продукта.
2. Исправление должно содержать reproduction/regression test, который падает до исправления.
3. Выборочный прогон используется для быстрой обратной связи, но не заменяет полный gate.
4. Native crash, зависание, collection error, непредусмотренный skip и изменение файлов тестом
   являются ошибками, даже если часть assertions прошла.
5. Synthetic fixtures проверяют границы, но критичные workflows дополнительно получают
   обезличенные реальные golden fixtures.
6. Source arrays/files не мутируются тестируемым calculation/render workflow.
7. Производительность проверяется отдельно от функциональной корректности; timing assertions не
   добавляются в обычные unit tests без контролируемой benchmark-среды.
8. После изменения проверяется актуальность `PROJECT_PLAN.md`, `ARCHITECTURE.md`, этого документа,
   RU/KK/EN-инструкций и `CHANGELOG.md`.

## 2. Подготовка Windows-окружения

```powershell
py -3.11 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -e ".[dev]"
```

Release runtime устанавливается из хешированного lock-файла:

```powershell
uv venv .venv --python 3.11
uv pip sync requirements/release.lock --python .venv --require-hashes
uv pip install --python .venv --no-deps --no-build-isolation --editable .
```

Канонический запуск:

```powershell
$env:PYTHONPATH = "$PWD\src"
python -m geoworkbench.app.main
```

`python -m geoworkbench` не является поддерживаемым entry point, пока пакет не содержит
`geoworkbench/__main__.py`.

## 3. Быстрый обязательный gate

После точечного изменения сначала выполняются связанные tests, затем:

```powershell
$env:PYTHONUTF8 = "1"
python tools/check_documentation.py
python -m compileall -q src tests tools scripts
python -m ruff check src tests tools scripts
python -m mypy src
```

Для текущего gas-conditioning инкремента минимальный набор:

```powershell
python -m pytest -q -p no:cacheprovider `
  tests/test_gas_conditioning.py `
  tests/test_project_session_gas_ratios.py `
  tests/test_gas_curve_rendering_continuity.py `
  tests/test_complex_gas_form.py `
  tests/test_a4_factory_templates.py
```

## 4. Полный автоматический gate

```powershell
$env:PYTHONUTF8 = "1"
python tools/check_documentation.py
python -m ruff check src tests tools scripts
python -m mypy src
python scripts/run_tests.py -p no:cacheprovider
```

Каждая команда должна завершиться кодом `0`. `scripts/run_tests.py` отключает случайные глобальные
pytest plugins, явно загружает проектный async plugin и изолирует известные нативные Qt lifecycle
cases. Изоляция допустима только для подтверждённой ошибки teardown; функциональный test при этом
не пропускается и должен выполняться в отдельном процессе.

## 5. Матрица тестов по слоям

### Domain и calculations

Проверяются:

- типы, формы массивов и версии контрактов;
- `NaN`, `inf`, реальные нули и нулевые знаменатели;
- возрастающие, убывающие, duplicate и mixed axes;
- immutable input и отсутствие скрытого in-place изменения;
- формулы и единицы;
- deterministic recalculation;
- positive, boundary и negative cases.

### Application/controllers/session

Проверяются:

- validation до commit;
- dirty-state;
- provenance;
- повторный запуск без дубликатов;
- transaction/rollback;
- корректный current well/dataset context;
- отсутствие частичного результата после exception/cancel.

### UI/Qt

Проверяются:

- создание/удаление widget tree;
- form switch и повторный import;
- selection/edit lifecycle;
- DPI 100/125/150/200%;
- keyboard/mouse routing;
- отсутствие `Internal C++ object already deleted`, native crash и leaked modal dialogs.

### Rendering и output

Проверяются одинаковые:

- resolved dataset/index/range;
- curve IDs и units;
- finite/gap semantics;
- segment boundaries;
- logarithmic zero policy;
- annotations/layout;
- screen, preview, PDF и printer page count.

### Storage/migrations

Проверяются round-trip, unknown fields, старые версии, atomic replace, failed migration rollback,
asset fingerprints и невозможность traversal/absolute-path dependency.

### Security

Проверяются bounded file/XML/archive/network input, secret redaction, dependency lock/SBOM,
небезопасные пути, DTD/entities, oversized payload, CIDR policy и fail-closed behavior.

### Performance

Benchmark фиксирует размер, время, p50/p95, scaling ratio, allocations/peak RSS и cache hit ratio.
Обычный unit test не должен падать из-за нагрузки CI runner; performance regression имеет
отдельные threshold и baseline artifacts.

## 6. Газовый conditioning и Gas Ratio

### Обязательные инварианты

- source C1–C5 и depth не изменяются;
- case-insensitive duplicate mnemonics отклоняются;
- increasing/descending/duplicate depth поддерживаются;
- mixed/nonfinite axis отклоняется;
- короткий bounded gap интерполируется;
- длинный outage, leading и trailing gap остаются `NaN`;
- конечный zero не перезаписывается;
- C4/C5 не учитываются дважды;
- расчёт выполняется после conditioning;
- `TG_CALC`, `*_REL`, Haworth, isomer и Pixler сохраняют исходный порядок строк;
- сумма доступных relative components равна 100% на валидной строке;
- zero denominator не создаёт infinity;
- recalculation обновляет существующую curve ID;
- provenance соответствует версии calculation profile.

### Текущие regression tests

- `tests/test_gas_conditioning.py` — policy, axes, duplicate depths, gaps, masks и derived ratios;
- `tests/test_project_session_gas_ratios.py` — реальный session boundary, source immutability,
  provenance и recalculation;
- `tests/test_gas_curve_rendering_continuity.py` — gas-only render policy, viewport/page context,
  log zero и relative stack;
- `tests/test_complex_gas_form.py` — C1–C5/Haworth/Pixler bindings и A4 layout;
- `tests/test_a4_factory_templates.py` — A4 fit и catalog contract.

### Следующие обязательные fixtures

- обезличенный интервал `1703.28–1753.28 м` с редкими C1–C5;
- длинная реальная остановка газовой регистрации;
- aggregate C4/C5 и split iC/nC в одном файле;
- descending LAS и duplicate depth rows;
- page boundary, проходящая внутри непрерывного газового сегмента;
- 100k/1M benchmark без O(N²) и неконтролируемого RSS.

Golden fixture должен хранить source values, ожидаемые interpolation masks, derived values и
segment/page expectations. Он не должен содержать данные заказчика или реальные идентификаторы.

## 7. Проверка комплексной газовой формы

Ручной smoke после пересчёта:

1. Открыть dataset и выполнить **«Рассчитать базовые Gas Ratio»**.
2. Применить A4 portrait и landscape комплексные газовые формы.
3. Проверить единый видимый depth track и семь графических секций.
4. Проверить, что header font относительного газа совпадает с соседними колонками.
5. На коротких sparse intervals кривые должны быть связными; длинный outage остаётся пустым.
6. Одиночная точка не должна визуально превращаться в длинный сегмент.
7. Проверить логарифмические Pixler/Haworth: zero/negative скрыты как gap, infinity отсутствует.
8. Сформировать preview/PDF и сравнить границы сегментов с экраном.
9. Проверить первую и последнюю страницу, page boundary и отсутствие clipping по X/Y.

Старый PDF не обновляется автоматически: после изменения calculations/rendering он формируется
заново из пересчитанного Dataset.

## 8. Windows GUI/HiDPI/PDF acceptance

`tools/windows_release_matrix.py` выполняется отдельно для scale factors `1.0`, `1.25`, `1.5`,
`2.0` и проверяет A4/A3/roll, portrait/landscape, Fit/100%, continuation pages, RU/KK/EN и
повторное чтение PDF.

```powershell
python tools/windows_release_matrix.py `
  --scale-factor 1.25 `
  --platform windows `
  --output-dir build/ci-artifacts/windows-acceptance/1_25
```

Автоматическая матрица не подтверждает фактическую печать. Physical-printer acceptance требует
явного принтера, оператора, отправки задания и визуального подтверждения:

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

## 9. Security gate

```powershell
python tools/release_security_gate.py
```

Gate создаёт dependency audit, CycloneDX SBOM, secret scan, Bandit report и manifest только в
игнорируемом `build/ci-artifacts/security`. Artifact не коммитится. Ошибка любой команды остаётся
ошибкой job, даже если upload artifacts выполнился.

## 10. Headless reduced-environment gate

```powershell
python scripts/run_headless_tests.py
```

Он используется только когда отсутствуют PySide6/pyqtgraph/lasio. Collection error по любой
другой причине фатален. Headless gate не заменяет Windows Qt test suite.

## 11. Performance gates

Acquisition:

```powershell
python benchmarks/benchmark_acquisition.py 50000 100000
```

Для gas conditioning должен быть добавлен отдельный benchmark 100k/1M, который измеряет:

- conditioning семи компонентов;
- полный derived ratio profile;
- scaling `T(2N)/T(N)`;
- peak RSS;
- долю интерполированных строк;
- повторный viewport render/cache hit без полного пересчёта Dataset.

До закрепления стабильной benchmark-среды threshold хранится в `PROJECT_PLAN.md`, а не в
случайном wall-clock assertion unit test.

## 12. CI и artifacts

`.github/workflows/release-gate.yml` запускает:

- Windows quality gate;
- Windows GUI/HiDPI/PDF acceptance;
- Windows dependency and source security gate.

Логи и evidence загружаются как artifacts с ограниченным retention. Временные workflow,
одноразовые trigger-файлы и patch scripts после инкремента не должны оставаться в `main`.

## 13. Действия при падении

1. Зафиксировать commit SHA, job, первый реальный error и полный traceback/log artifact.
2. Отделить assertion failure, collection error, type/lint error, native crash, timeout и
   environment failure.
3. Воспроизвести минимальным test command.
4. Добавить regression test либо усилить существующий контракт.
5. Исправить production boundary; не маскировать ошибку изменением ожидаемого значения без
   подтверждённого изменения продукта.
6. Запустить связанный набор, затем полный gate.
7. Удалить временные ветки, workflows, triggers, artifacts и проверить чистый `main`.

## 14. Критерий готовности

Инкремент готов, когда код, tests, docs и changelog согласованы; полный применимый gate зелёный;
ручные обязательные проверки отмечены как выполненные либо явно остаются открытым пунктом плана;
source data не повреждены; нет временного мусора; локальный и удалённый `main` синхронизированы.
