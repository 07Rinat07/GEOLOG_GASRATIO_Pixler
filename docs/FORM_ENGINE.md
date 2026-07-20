# Form Engine

Form Engine stores editable depth and time forms independently from a concrete LAS file.
A form references canonical parameters. The mnemonic dictionary resolves those parameters to
curves in the currently opened dataset.

## Implemented first slice

- versioned form schema v1;
- form, column, track and parameter-binding models;
- depth and time form types;
- validation of identifiers, widths, ranges and duplicate links;
- UTF-8 JSON serialization and migration from schema v0;
- atomic repository for user forms;
- read-only factory templates and editable copies;
- factory templates: basic depth, basic time, gas components, Gas Ratio, Pixler and interpretation.

The visual form editor is not part of this slice. It will use these models as the single source
of truth.

## Визуальный редактор структуры формы

Менеджер форм открывает пользовательскую форму в редакторе структуры. Редактор поддерживает добавление, удаление и перестановку колонок и дорожек, изменение ширины колонок, редактирование заголовков и типа дорожки, предпросмотр и сохранение в JSON. Заводские формы защищены и редактируются только через пользовательскую копию.

## Редактор содержимого дорожки

Для выбранной дорожки открывается отдельный редактор параметров. Он поддерживает:

- добавление канонического параметра из Sensors-каталога;
- добавление конкретной кривой текущего LAS;
- удаление и изменение порядка `ParameterBinding`;
- отображаемое имя, канонический идентификатор, исходную мнемонику и единицу;
- видимость, цвет, толщину и стиль линии;
- линейную или логарифмическую шкалу;
- автоматический или ручной диапазон.

Изменения сохраняются в пользовательском JSON-шаблоне и применяются через существующий Form Apply Engine. Исходные данные LAS не переименовываются и не изменяются.


## Live Form Preview
Редактор работает с безопасной draft-копией формы. Изменения могут автоматически применяться к рабочему планшету или оставаться в памяти до команды «Применить». Команды «Сохранить» и «Отменить изменения» не требуют повторного открытия менеджера форм.

## Specialized Gas Ratio & Pixler factory forms

The factory library now includes localized depth interpretation, time monitoring, normalized-gas
QC, and detailed C1–C5 forms. Captions are generated in RU/KK/EN while stable form, column,
track, binding, and canonical-parameter identifiers remain unchanged.

## Dataset-aware working LAS forms

The generic depth and time factory forms are no longer empty placeholders. When a dataset is open,
they are materialized from its real LAS curves, grouped into readable drilling, mud, gas,
petrophysics, D-exponent, and other columns with no more than four curves per column. Every
binding keeps the exact source mnemonic, description, unit, catalog color, and recommended range.
The factory form can be opened directly or converted into an editable user copy. The manager shows
available/missing curves and blocks forms whose depth/time axis is incompatible with the dataset.
## Working LAS form rendering hotfix

Fixed the failure that left the tablet empty after a form was selected. A safe default curve
style is now created correctly, and `PlotDataItem` construction is compatible with
`pyqtgraph 0.14` and `PySide6 6.11`. A GUI regression test now requires the factory depth
form to materialize and actually render the curves of the open LAS dataset.

