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

- импорт и проверка LAS, CSV, GeoScape/Paradox DB и таблиц контейнера GeoScape II GS2;
- безопасный инвентарь WITSML 2.x, WITS0 TCP client/server, типизированный parser и Import Review с immutable schema;
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
- [Общий план интеграции WITS0/WITSML](docs/WITS_INTEGRATION_PLAN.md)
- [История изменений](docs/CHANGELOG.md)
- [Проверка качества](docs/TESTING.md)

## Автор

Rinat Sarmuldin (Сармулдин Ринат) — ura07srr@gmail.com

## Лицензия

Условия распространения указаны в [LICENSE](LICENSE).

## ETP 1.2

Version 0.7.82 extends the secure WITSML 2.x / ETP 1.2 client with URI-stable ChannelData Import Review, normalized batches, append-only acquisition, reconnect overlap deduplication, while retaining Discovery, Store,
Data Array, Channel Subscribe, reconnect recovery and a non-blocking desktop browser. See
`docs/ETP12_ARCHITECTURE.md` and `docs/ETP12_INTEROPERABILITY_GATE.md`.
