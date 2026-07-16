# Аудит официальной документации по построению графиков

Проверено 16 июля 2026 года. Используются первичные документы библиотек проекта.

## PyQtGraph

- `PlotDataItem` — основной API для кривых и scatter-графиков:
  https://pyqtgraph.readthedocs.io/en/latest/api_reference/graphicsItems/plotdataitem.html
- Для плотных данных поддерживаются `setClipToView()` и `setDownsampling()`.
- Метод downsampling `peak` сохраняет локальные минимумы и максимумы и предпочтителен для
  инженерных кривых при обзорном масштабе. Исходный массив остаётся источником расчётов и экспорта.
- `skipFiniteCheck` нельзя включать для импортированных данных без предварительной гарантии
  конечности: официальная документация предупреждает о сбоях на `NaN`/`Inf`.
- `DateAxisItem` форматирует Unix timestamps в зависимости от плотности времени:
  https://pyqtgraph.readthedocs.io/en/latest/api_reference/graphicsItems/dateaxisitem.html
  Он подходит для будущего Time View, но не заменяет явное TIME↔DEPTH сопоставление.

## Qt Paint System

- `QPainter` предоставляет `setClipRect()`/`setClipPath()`:
  https://doc.qt.io/qtforpython-6/PySide6/QtGui/QPainter.html
- `QPainterPath` предназначен для переиспользуемых векторных контуров:
  https://doc.qt.io/qtforpython-6/PySide6/QtGui/QPainterPath.html
- Печатный renderer продолжает применять clipping на уровне колонки/страницы и не зависит от
  экранного масштаба.

## NumPy datetime

- Нормализованное абсолютное время хранится как `datetime64[ns]`:
  https://numpy.org/doc/stable/reference/arrays.datetime.html
- Поиск временной позиции не должен молча интерполировать повторные проходы. Реализованный
  TIME↔DEPTH resolver выбирает ближайшую строку только при однозначной глубине и блокирует ties.

## Решения для roadmap

1. Добавить `clipToView=True` и автоматический `peak` downsampling в интерактивные Curve View после
   benchmark на больших LAS; печать и экспорт продолжают использовать исходные данные.
2. Не включать `skipFiniteCheck` для пользовательских datasets.
3. Для Time View использовать `DateAxisItem` поверх UTC/явно нормализованной шкалы.
4. Сохранять TIME↔DEPTH policy явно; неоднозначные индексы требуют выбора пользователя.
