# GEOLOG GASRATIO@Pixler 0.7.90 — синхронизация документации и тестового gate

## Исправлено

- Основная команда запуска во всех текущих инструкциях заменена на
  `python -m geoworkbench.app.main`.
- Корневой README приведён к фактическому способу установки, запуска и быстрой проверки.
- Из RU/KK/EN-руководств удалены устаревшие стартовые блоки 0.7.70–0.7.73; руководство снова
  является текущей пользовательской инструкцией, а не журналом старых изменений.
- `docs/TESTING.md` переписан как один действующий release gate с быстрым набором, полным
  автоматическим прогоном и ручной Windows GUI-приёмкой.
- `DOCUMENTATION_INDEX.md` больше не называет 0.7.80 текущей сборкой и ведёт на документы 0.7.90.
- `PROJECT_STATUS`, `REQUIREMENTS`, `ROADMAP` и `DOCUMENTATION_POLICY` синхронизированы с новым
  контрактом запуска и проверки.

## Автоматическая защита от повторения ошибки

- `tools/check_documentation.py` проверяет наличие канонической команды запуска в корневом README,
  RU/KK/EN-руководствах и `docs/TESTING.md`.
- Audit проверяет, что текущий documentation index ссылается на release notes и build manifest
  версии из `pyproject.toml`.
- Добавлен `tests/test_module_entrypoint_contract_0790.py`, который статически проверяет
  `__main__`-guard и соответствие `[project.scripts]` функции `geoworkbench.app.main:main` без
  импорта PySide6.
- Расширены `test_documentation_sync_0762.py` и `test_root_readme_scope.py`.
- Исправлен штатный `scripts/run_tests.py`: при отключённом autoload он теперь явно загружает `pytest_asyncio.plugin`; `pytest-asyncio` добавлен в dev dependencies.
- Добавлен `scripts/run_headless_tests.py`, который не скрывает неизвестные collection-ошибки и исключает только тесты, заблокированные отсутствующими PySide6/pyqtgraph/lasio.
- Удалён устаревший тестовый контракт с жёстко зафиксированной версией 0.7.83; версия берётся из пакета.

## Совместимость

Код импорта и отображения данных не менялся. Исправления 0.7.87–0.7.89 сохранены. Форматы остаются:
project v21, form schema v9, tablet layout v19.
