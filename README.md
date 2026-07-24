# GEOLOG GASRATIO@Pixler

<p align="center">
  <img
    src="src/geoworkbench/resources/geologist-logo.png"
    alt="GEOLOGIST — Offshore Exploration"
    width="460"
  >
</p>

Настольное приложение для работы с LAS и геолого-технологическими данными: просмотр и
безопасное редактирование кривых, многотрековые планшеты, интервальная геология, расчёты,
редактируемые формы Masterlog, PDF и печать.

Основные возможности:

- импорт и проверка LAS, CSV и GeoScape/Paradox DB;
- глубинные и временные datasets с безопасным наращиванием данных;
- настраиваемые многоколонные планшеты и повторно используемые рабочие формы;
- редактирование кривых, интервальные объекты, комментарии и обозначения;
- расчёты газового каротажа и производные кривые;
- экспорт, предварительный просмотр и печать отчётов;
- интерфейс и пользовательская документация на русском, казахском и английском языках.

Статус проекта: активная разработка.

## Запуск

Требуется Python 3.11 или новее.

### Windows

```powershell
py -3.11 -m venv .venv
.venv\Scripts\activate
python -m pip install --upgrade pip
pip install -e ".[dev]"
geolog-gasratio-pixler
```

### Linux

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -e ".[dev]"
geolog-gasratio-pixler
```

## Документация

- [Русское руководство](docs/ru/README.md)
- [Қазақша нұсқаулық](docs/kk/README.md)
- [English guide](docs/en/README.md)
- [Указатель документации](docs/DOCUMENTATION_INDEX.md)
- [Статус проекта](docs/PROJECT_STATUS.md)
- [План разработки](docs/PROJECT_PLAN.md)
- [История изменений](docs/CHANGELOG.md)
- [Проверка качества](docs/TESTING.md)

## Автор

Rinat Sarmuldin (Сармулдин Ринат) — ura07srr@gmail.com

## Лицензия

Условия распространения указаны в [LICENSE](LICENSE).
