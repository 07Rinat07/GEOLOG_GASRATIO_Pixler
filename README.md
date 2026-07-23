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

Текущая тестовая версия: **0.7.44**. Добавлена версионированная lag/depth correction с неизменяемым acquisition source, ревизиями и выбором исходной либо скорректированной оси.

Основные принципы проекта:

- исходные файлы не изменяются скрытно;
- экранная форма, preview и печать используют общую модель;
- проекты и формы мигрируют между версиями;
- интерфейс и пользовательские инструкции поддерживаются на русском, казахском и английском;
- готовность выпуска определяется полным набором проверок, а не номером версии.

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

Планы, история выпусков и технические отчёты находятся в `docs`, а не в README.

## Автор

Rinat Sarmuldin (Сармулдин Ринат) — ura07srr@gmail.com

## Лицензия

Условия распространения указаны в [LICENSE](LICENSE).
