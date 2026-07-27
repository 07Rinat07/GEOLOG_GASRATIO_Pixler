# HOTFIX 0.7.90 — документация, запуск и тестовый контур

## Обнаруженные проблемы

1. В корневом `README.md` основным запуском был указан console script
   `geolog-gasratio-pixler`, хотя фактическая рабочая команда проекта —
   `python -m geoworkbench.app.main`.
2. Локализованные RU/KK/EN README начинались с исторических блоков 0.7.70–0.7.73 и не содержали
   полноценной команды установки и запуска.
3. `DOCUMENTATION_INDEX.md` продолжал отмечать версию 0.7.80 как текущую.
4. `docs/TESTING.md` содержал накопленные исторические срезы вместо одного действующего gate.
5. Изолированный `scripts/run_tests.py` отключал autoload всех pytest-плагинов, но не загружал
   `pytest_asyncio` явно. Шесть async ETP-тестов из-за этого фактически падали.
6. `tests/test_etp12_source_contracts.py` жёстко требовал версию 0.7.83 и ломался при любом
   корректном повышении версии.
7. Acquisition callbacks в `MainWindow` напрямую меняли `session.dirty`, нарушая уже существующий
   project-boundary regression-контракт.
8. В среде без PySide6/pyqtgraph/lasio полный collection завершался множеством import errors,
   поэтому не было воспроизводимого reduced-environment test command.

## Исправления

- Каноническая команда запуска синхронизирована во всех текущих инструкциях:

  ```powershell
  python -m geoworkbench.app.main
  ```

- Обновлены корневой README, RU/KK/EN README, `TESTING.md`, `DOCUMENTATION_INDEX.md`,
  `DOCUMENTATION_POLICY.md`, `PROJECT_STATUS.md`, `REQUIREMENTS.md`, `ROADMAP.md` и `CHANGELOG.md`.
- `tools/check_documentation.py` теперь проверяет:
  - команду запуска;
  - исполняемый `__main__`-guard;
  - согласованность package entry points;
  - ссылки current build на release notes и build manifest текущей версии;
  - наличие действующего тестового контура.
- Добавлены regression-тесты:
  - `test_module_entrypoint_contract_0790.py`;
  - `test_test_runner_contract_0790.py`;
  - дополнительные проверки в `test_documentation_sync_0762.py` и
    `test_root_readme_scope.py`.
- В `pyproject.toml` добавлен `pytest-asyncio>=0.23`.
- `scripts/run_tests.py` при отключённом global plugin autoload явно загружает
  `pytest_asyncio.plugin`.
- Добавлен `scripts/run_headless_tests.py`. Он исключает test file только при подтверждённом
  отсутствии PySide6, pyqtgraph или lasio; неизвестная collection-ошибка остаётся фатальной.
- Версионный source-contract теперь использует `geoworkbench.__version__`, а не литерал 0.7.83.
- Выбор изменившегося acquisition dataset и dirty-state перенесены в `ProjectController`.
- `qapp` и LAS round-trip тесты корректно используют skip, когда соответствующая зависимость
  отсутствует в reduced environment.

## Совместимость

Форматы данных не менялись:

- project format: v21;
- form schema: v9;
- tablet layout: v19.

Исправления 0.7.87–0.7.89 остаются в проекте без изменения поведения импорта и отображения данных.
