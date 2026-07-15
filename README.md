# GEOLOG GASRATIO@Pixler

<p align="center">
  <img
    src="src/geoworkbench/resources/geologist-logo.png"
    alt="GEOLOGIST — Offshore Exploration"
    width="460"
  >
</p>

Расширяемое настольное приложение для работы с LAS/ГИС, ГТИ, газовым каротажем,
литологией, шламограммой, стратиграфией, корреляцией скважин и печатью мастерлогов.

Фирменный логотип включён в пакет приложения, используется как иконка окна и отображается
в диалоге «О программе». Правила хранения описаны в [документе о брендинге](docs/BRANDING.md).

## Текущая версия: 0.6.0

Реализовано:

- главное окно на PySide6;
- загрузка одного или нескольких LAS-файлов;
- импорт числовых CSV/TXT с предпросмотром, выбором кодировки, разделителя и индексной
  колонки, поддержкой единиц в заголовках и NULL-маркеров;
- ISO-8601 и составной `DATE + TIME` индекс CSV/TXT с настраиваемыми форматами,
  безопасной UTC-нормализацией и сохранением timezone provenance;
- импорт XLSX/XLSM через встроенную команду с выбором листа, строки заголовка и индекса;
- дерево проекта, скважин, наборов данных и кривых;
- интерактивный просмотр кривых через PyQtGraph;
- базовые Gas Ratio: C1/C2, C1/C3, C2/C3, C1/(C2+C3);
- расчётная сумма доступных C1–C5-компонентов;
- атомарное сохранение проекта в JSON;
- открытие ранее сохранённых проектов и совместимое чтение legacy JSON;
- сохранение отдельной компоновки планшета для каждого набора данных;
- линейная и логарифмическая шкалы X с автоматическим или фиксированным диапазоном;
- легенды кривых с единицами измерения;
- изменение ширины треков через меню и перетаскиванием границы;
- редактирование ширины, шкалы и диапазона X через инспектор;
- сохранение видимого интервала глубины для каждого набора данных;
- отрисовка видимого диапазона с ограничением числа точек для больших LAS;
- фундамент многотрекового планшета;
- общая синхронизированная шкала глубины;
- горизонтальная компоновка треков и прокрутка;
- базовые треки глубины, газа и отдельных кривых;
- переключение наборов данных из дерева проекта;
- реестр версионируемых формул Pixler без непроверенных встроенных формул;
- автоматические тесты ядра, хранения, Plugin API и headless Qt-сценариев.
- командное ядро редактирования кривых с Undo/Redo, конфликтами и инвалидированием зависимостей.
- инструмент карандаша для выбранной кривой и горячие клавиши Undo/Redo.
- атомарный экспорт изменённого dataset в новый LAS без перезаписи источника.
- строгие паспорта расчётных формул с источниками, единицами и контрольными примерами.
- встроенный справочник пород и редактор проектных литотипов с кодами, выбором цвета и предпросмотром узоров.
- планшетный трек литологии с цветами и масштабируемыми условными узорами.
- коды пород внутри литологического трека и легенда используемых литотипов.
- синхронизированный трек текстовых описаний литологических интервалов.
- адаптивные подписи литологии, скрывающиеся на недостаточном масштабе.
- проектные шаблоны описаний пород с быстрым применением в редакторе интервалов.
- дерево литологических интервалов, заметок, шаблонов и упорядоченных слоёв планшета.
- диагностика направления и произвольного шага глубины, безопасная возрастающая копия GIS LAS.
- диапазонные операции LAS Editor и экспорт выбранных глубин/параметров в TXT, CSV и Excel.
- виртуальная вкладка LAS-таблицы с ручным вводом и немедленным пересчётом газовых кривых.
- диагностируемый импорт LAS с SHA-256 отпечатком источника, версией, WRAP, NULL,
  направлением индекса, дубликатами и проверкой STRT/STOP/STEP.
- байт-сохраняющий `LosslessLasDocument` с кодировкой, переводами строк, исходным
  порядком и точными границами секций LAS.
- проверяемое `.assets`-хранилище оригинальных LAS рядом с проектом без помещения байтов в JSON.
- lossless-aware экспорт новой LAS-копии с обновлением стандартных и побайтным переносом
  пользовательских секций, комментариев, BOM и стиля строк.
- диалог `ExportPlan` для LAS 1.2/2.0, WRAP, NULL и точности с анализом ошибок и потерь до записи.
- типизированные индексы MD/TVD/TVDSS/TIME/DATETIME/GENERIC, безопасный active index и
  распознавание кандидатов с confidence, evidence и warnings.
- Data Inspector со сводкой WELL, индексами, кривыми, диагностикой импорта и ручным выбором
  active index без удаления остальных колонок.
- безопасный редактор VERSION/WELL/PARAMETER с Undo/Redo, проверкой координат и
  синхронизацией имени скважины; VERS/WRAP и STRT/STOP/STEP/NULL защищены от
  рассогласования с планом экспорта и данными.
- вычисляемая сводка STRT/STOP/STEP, безопасная синхронизация равномерной глубины и
  проверяемый NULL, автоматически используемый планом LAS-экспорта.
- редактор каталога кривых: мнемоника, единица и описание с проверкой конфликтов,
  сохранением канонической идентичности и отдельными Undo/Redo.
- профиль LAS-источника с версией, WRAP, NULL, кодировкой, секциями, SHA-256 и состоянием
  lossless-артефакта; совместимые параметры автоматически предлагаются при экспорте.
- явные режимы LAS-импорта: строгий, совместимый и ручная проверка с подтверждением каждого
  проблемного файла по единому структурированному отчёту.
- распознавание ISO-8601, Unix s/ms/us/ns и datetime64 с явным timezone provenance;
  время без зоны не подменяется UTC и отображается с предупреждением.
- нормализация составных DATE+TIME и пользовательских `strptime`-форматов с IANA timezone
  или фиксированным UTC offset; неоднозначные DST-моменты блокируются.
- персистентный import provenance проекта v7 с проверкой отчёта по SHA-256 lossless-источника.

## Запуск в Windows

```powershell
py -3.11 -m venv .venv
.venv\Scripts\activate
python -m pip install --upgrade pip
pip install -e ".[dev]"
geolog-gasratio-pixler
```

## Локальный запуск в Linux

Для Debian/Ubuntu сначала установите Python и системные библиотеки, необходимые Qt:

```bash
sudo apt update
sudo apt install -y \
  python3 python3-venv python3-pip \
  libgl1 libegl1 libxkbcommon-x11-0 libxcb-cursor0
```

Перейдите в каталог проекта, создайте виртуальное окружение и установите зависимости:

```bash
cd GEOLOG_GASRATIO_Pixler
python3 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -e ".[dev]"
```

Запустите приложение:

```bash
geolog-gasratio-pixler
```

При следующих запусках достаточно активировать уже созданное окружение:

```bash
cd GEOLOG_GASRATIO_Pixler
source .venv/bin/activate
geolog-gasratio-pixler
```

Если приложение запускается на сервере без графической сессии, окно Qt не откроется.
Для обычного локального запуска должен быть доступен дисплей X11 или Wayland.

## Среда разработки

После создания и активации виртуального окружения установите runtime- и
dev-зависимости одной командой:

```bash
python -m pip install -e ".[dev]"
```

Основные проверки:

```bash
pytest -q
ruff check src tests
mypy src
```

Правила, матрица и обязательный процесс тестирования описаны в
[`docs/TESTING.md`](docs/TESTING.md).

## Документация

Подробный план, архитектура и описание инкрементов находятся в каталоге `docs/`.
Единая [матрица требований](docs/REQUIREMENTS.md) фиксирует поддерживаемые форматы,
редактирование, визуализацию, экспорт и печать; порядок реализации описан в
[roadmap](docs/ROADMAP.md).
Архитектура LAS с глубинными, временными и несколькими индексами описана в
[отдельной спецификации](docs/TIME_DEPTH_LAS_ARCHITECTURE.md).
Текущее поведение редактора описано в [инструкции LAS Editor](docs/LAS_EDITOR.md).
Правила диагностики при открытии файлов описаны в
[инструкции импорта LAS](docs/LAS_IMPORT.md).

## Автор

**Сармулдин Ринат**  
E-mail: **ura07srr@gmail.com**

## Статус

Проект находится в активной разработке. Формулы Pixler, Wetness, Balance, Character,
коэффициента флюидности и D-экспоненты добавляются только после фиксации источника,
единиц измерения и контрольного примера.

## Proprietary License

Copyright (c) 2026 Rinat Sarmuldin

All rights reserved.

### 1. Ownership

The source code, assets, documentation, and all related materials in this repository
("Software") are proprietary and owned by Rinat Sarmuldin.

### 2. No automatic grant of rights

No right, license, or permission is granted to use, copy, modify, merge, publish,
distribute, sublicense, sell, or create derivative works of the Software, in whole or
in part, without prior written permission from the copyright owner.

### 3. Allowed without separate agreement

You may view this repository and clone/download it only for personal, non-commercial,
read-only evaluation.

### 4. Commercial and production use

Any commercial use, internal company use, SaaS use, production deployment, redistribution,
or modification requires prior written permission from the copyright owner.

### 5. Third-party components

Third-party libraries and tools included in this project are subject to their own
licenses. This license does not limit rights granted by those third-party licenses.

### 6. Warranty disclaimer

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR IMPLIED,
INCLUDING BUT NOT LIMITED TO WARRANTIES OF MERCHANTABILITY, FITNESS FOR A PARTICULAR
PURPOSE, AND NON-INFRINGEMENT.

### 7. Contact for permissions

For licensing and usage permissions, contact: ura07srr@gmail.com
