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

