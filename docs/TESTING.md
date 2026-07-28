# Проверка качества и release gate

Документ актуален для **GEOLOG GASRATIO@Pixler 0.7.93**. Краткая история находится только в
`CHANGELOG.md`; результаты конкретных CI/сборок хранятся как artifacts и не заменяют текущие
команды проверки.

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
- отсутствие синтаксических ошибок в Python-модулях.

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

Workflow `.github/workflows/release-gate.yml` отдельно выполняет полный Windows quality gate и
Linux security gate. Логи качества и security reports загружаются как два CI artifact с retention
30 дней. Artifact не коммитится и не считается успешным gate, если соответствующая команда
завершилась ненулевым кодом.

## 6. Ручная Windows-приёмка GUI

Автоматические source-contract и headless-тесты не заменяют проверку настоящего интерфейса.
Минимальный smoke-сценарий:

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

## 7. Правило обновления тестов и документации

Любое изменение запуска, импорта, формы, миграции, формата проекта или пользовательского
поведения должно в одном изменении обновлять:

- код;
- regression-тест;
- корневой README, если изменился запуск или базовый workflow;
- соответствующие RU/KK/EN-инструкции;
- `CHANGELOG.md`;
- `tools/check_documentation.py`, если новый контракт можно проверить автоматически.

Версия не считается готовой только по `compileall` или нескольким выбранным тестам. В CI artifact
должны быть отдельно указаны реально выполненные проверки и проверки, которые не могли быть
выполнены в текущей среде.
