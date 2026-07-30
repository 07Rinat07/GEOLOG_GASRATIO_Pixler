# GEOLOG GASRATIO@Pixler

Настольная платформа для подготовки, проверки, интерпретации и визуализации буровых,
газокаротажных, LAS- и GeoScape2/GS2-данных. Приложение объединяет работу с исходными данными,
многотрековыми планшетами, инженерными расчётами, формами Masterlog и выпуском отчётов в одном
проекте.

[Русское руководство](docs/ru/README.md) ·
[Қазақша нұсқаулық](docs/kk/README.md) ·
[English guide](docs/en/README.md)

Рабочая модель приложения проектная: исходные LAS/GS2/DB остаются неизменяемыми источниками,
вся продолжаемая работа сохраняется в проекте скважины, а LAS создаётся отдельным экспортом.
Подробный ежедневный процесс: [RU](docs/ru/PROJECT_WORKFLOW.md) ·
[KK](docs/kk/PROJECT_WORKFLOW.md) · [EN](docs/en/PROJECT_WORKFLOW.md).

## Основные возможности

- **Импорт и проверка данных.** LAS 1.2/2.0, CSV/TXT, Excel, GeoScape2/GS2, Paradox и SKF с
  предварительным просмотром, сопоставлением каналов и диагностикой NULL, единиц, индексов и
  дубликатов.
- **Полный цикл работы с LAS.** Создание, открытие, табличное редактирование, объединение наборов,
  ежедневное наращивание, перенос кривых, изменение шага и экспорт без изменения исходного файла.
- **Потоковые и отраслевые форматы.** Захват WITS0 в режимах TCP client/server с сохранением raw и
  replay; локальный импорт WITSML 2.x ChannelSet и read-only-подключение к WITSML 1.4.1.1 SOAP.
- **Газовый каротаж и расчёты.** Gas Ratio, суммарный и нормализованный газ,
  Wetness/Balance/Character, коэффициенты Pixler, DEXP/NCT, интервальная статистика,
  lag/depth-коррекция и пользовательские формулы.
- **Визуализация и интерпретация.** Глубинные и временные многотрековые планшеты, редактирование
  кривых, шкалы и сетки, аннотации, литология, стратиграфия, образцы и операционные события.
- **Формы и Masterlog.** Заводские и пользовательские шаблоны, библиотека форм, конструктор колонок
  и шапок, условные обозначения, изображения и воспроизводимое сохранение структуры.
- **Отчёты и печать.** Предварительный просмотр, A4/A3/рулонные носители, физическая печать и
  экспорт в PDF, PNG, JPEG, TIFF, BMP, WebP, SVG, CSV, XLSX, DOCX и HTML.
- **Рабочее пространство «Файлы».** Отдельная видимая вкладка для PDF и изображений,
  объединения и разделения PDF, экспорта текста в DOCX, логотипов, архивов, инженерного
  калькулятора, конвертера единиц и расчёта отметок datum/GL/wellhead/DF/RT/KB-RKB.
- **Три языка интерфейса.** Русский, қазақша и English с переключением во время работы и
  синхронизированной пользовательской документацией.

Полная карта функций и связанных инструкций находится в
[русском описании возможностей](docs/ru/FEATURES.md).

## Установка и запуск

Требуется Python **3.11 или новее**. Все команды выполняются из корня проекта. Отдельный Qt SDK
не нужен: необходимые компоненты Qt устанавливаются вместе с PySide6.

Примеры ниже устанавливают инструменты разработки и тестирования через extra `dev`. Если нужно
только запустить приложение, замените `-e ".[dev]"` на `-e .`.

### Windows 10/11 — PowerShell

```powershell
py -3.11 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -e ".[dev]"
python -m geoworkbench.app.main
```

Если установлена другая версия Python 3.11+, замените `-3.11` на её номер. Активация окружения

> **Важно после обновления через Git.** Команда `git pull` обновляет исходный код, но не устанавливает
> новые Python-зависимости. После каждого обновления, изменяющего `pyproject.toml`, выполните в активном
> виртуальном окружении `python -m pip install -e ".[dev]"`. Для вкладки «Файлы» требуются PyMuPDF
> (импортируется как `fitz`) и Pillow. Если они отсутствуют, приложение теперь запускается, а вкладка
> показывает команду восстановления окружения вместо аварийного завершения.

необязательна: при ограничениях PowerShell можно вызывать
`.\.venv\Scripts\python.exe` вместо `python`.

### Linux

Сначала убедитесь, что команда `python3 --version` показывает Python 3.11 или новее:

```bash
python3 --version
python3 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -e ".[dev]"
python -m geoworkbench.app.main
```

В дистрибутивах, где модуль `venv` поставляется отдельно, установите пакет для выбранной версии
Python, например `python3.11-venv`. Если Qt сообщает об ошибке плагина `xcb`, для Debian/Ubuntu
обычно требуются системные библиотеки `libegl1`, `libgl1`, `libxkbcommon-x11-0` и
`libxcb-cursor0`.

### macOS

Используйте установленный Python 3.11+ либо установите его через Homebrew:

```bash
brew install python@3.11
python3.11 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -e ".[dev]"
python -m geoworkbench.app.main
```

Если подходящий `python3` уже установлен, команды Homebrew и суффикс версии не нужны.

> Основной GUI- и release-gate проекта выполняется в Windows. Linux и macOS доступны для запуска
> из исходников; перед рабочим применением на них нужно отдельно проверить GUI, печать и подключение
> к полевым источникам на целевой машине.

### Дополнительные компоненты

- Для SciPy, pandas и Parquet установите аналитический набор:
  `python -m pip install -e ".[analysis]"`.
- Для разработки вместе с аналитическим набором используйте:
  `python -m pip install -e ".[dev,analysis]"`.
- LibreOffice Calc нужен только для чтения старых `.xls` и пересчёта формул Excel. Обычная работа
  с LAS, CSV/TXT и `.xlsx` без пересчёта формул его не требует.

## Проверка проекта

Минимальная проверка документации и ключевых контрактов:

```text
python tools/check_documentation.py
python -m pytest -q tests/test_module_entrypoint_contract_0790.py tests/test_test_runner_contract_0790.py tests/test_documentation_sync_0762.py
```

Полный тестовый прогон:

```text
python scripts/run_tests.py -p no:cacheprovider
```

Полный release-gate и ручная Windows-приёмка описаны в [docs/TESTING.md](docs/TESTING.md).

## Автор и разработчик

<p align="center">
  <img
    src="docs/assets/author-rinat-sarmuldin.png"
    alt="Rinat Sarmuldin — автор и разработчик GEOLOG GASRATIO@Pixler"
    width="720"
  >
</p>

<p align="center">
  <strong>Rinat Sarmuldin</strong><br>
  Автор и разработчик проекта GEOLOG GASRATIO@Pixler.
</p>

## Документация

- [Каталоги печатных шапок и логотипов](docs/PRINT_HEADER_AND_LOGO_CATALOGS.md)

- [Каталог документации](docs/DOCUMENTATION_INDEX.md)
- [Архитектура](docs/ARCHITECTURE.md)
- [Единый актуальный план проекта](docs/PROJECT_PLAN.md)
- [Политика безопасности и сообщение об уязвимости](SECURITY.md)
- [История изменений](docs/CHANGELOG.md)

## Лицензия

Условия распространения указаны в [LICENSE](LICENSE).
