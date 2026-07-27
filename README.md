# GEOLOG GASRATIO@Pixler

Настольное приложение для работы с LAS и геолого-технологическими данными.

Основные возможности:

- открытие, проверка, редактирование и объединение LAS;
- работа с глубинными и временными наборами данных;
- многотрековые планшеты и редактор кривых;
- расчёты газового каротажа;
- импорт WITS0 и WITSML;
- экспорт и печать отчётов;
- русский, казахский и английский интерфейс.

## Установка и запуск в Windows

Требуется Python 3.11 или новее.

```powershell
py -3.11 -m venv .venv
.venv\Scripts\activate
python -m pip install --upgrade pip
pip install -e ".[dev]"
geolog-gasratio-pixler
```

## Документация

- [Русское руководство](docs/ru/README.md)
- [Қазақша нұсқаулық](docs/kk/README.md)
- [English guide](docs/en/README.md)

## Лицензия

Условия распространения указаны в [LICENSE](LICENSE).
