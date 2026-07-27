# GEOLOG GASRATIO@Pixler

Настольное приложение для работы с LAS, GeoScape2/GS2 и геолого-технологическими данными.

Основные возможности:

- открытие, проверка, редактирование и объединение LAS;
- импорт глубинных и временных наборов данных, включая GeoScape2/GS2;
- многотрековые планшеты, формы и редактор кривых;
- расчёты газового каротажа, Gas Ratio и Pixler;
- импорт WITS0 и WITSML;
- экспорт и печать отчётов;
- русский, казахский и английский интерфейс.

## Установка в Windows

Требуется Python 3.11 или новее. Команды выполняются из корня проекта:

```powershell
py -3.11 -m venv .venv
.venv\Scripts\activate
python -m pip install --upgrade pip
python -m pip install -e ".[dev]"
```

## Запуск

Основной и проверяемый способ запуска проекта:

```powershell
python -m geoworkbench.app.main
```

Команду нужно выполнять из активированного виртуального окружения и из корня проекта.

## Проверка проекта

Быстрая проверка документации и ключевых регрессий:

```powershell
python tools/check_documentation.py
python -m pytest -q tests/test_module_entrypoint_contract_0790.py tests/test_test_runner_contract_0790.py tests/test_documentation_sync_0762.py
python scripts/run_headless_tests.py
```

Полный release gate описан в [docs/TESTING.md](docs/TESTING.md).

## Документация

- [Русское руководство](docs/ru/README.md)
- [Қазақша нұсқаулық](docs/kk/README.md)
- [English guide](docs/en/README.md)
- [Каталог документации](docs/DOCUMENTATION_INDEX.md)
- [История изменений](docs/CHANGELOG.md)

## Лицензия

Условия распространения указаны в [LICENSE](LICENSE).
