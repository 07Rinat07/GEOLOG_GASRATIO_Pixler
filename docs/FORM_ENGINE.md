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

## Adaptive A4 printing for all forms

The Form Manager now exposes A4 portrait/landscape selection and an automatic column-fit option.
The print renderer captures every visible track, including tracks outside the horizontal viewport,
normalizes extreme screen widths, preserves readable minima by track type, and applies one common
print scale. Preview and PDF export restore the original tablet widths after rendering.


## Universal Print and Export Center

All factory and user forms use one page renderer. Form Manager can send the selected compatible form directly to the Print and Export Center. The center supports native system printing, PDF, PNG, JPEG/JPG, TIFF, BMP, WebP, and SVG. Paper settings include A4, A3, custom and roll sizes, portrait/landscape orientation, four independent margins, 72–600 DPI, and JPEG/WebP quality. Raster outputs are created at the physical paper pixel size for the requested DPI. Every visible form track is included even when it is outside the horizontal screen viewport; temporary print widths are restored after rendering.

## GeoData depth workspace — current form slice

The user-visible factory library is curated to three working forms: GeoData Depth Workspace,
Geological-Geochemical Masterlog, and Engineering Control — Time. Legacy factory IDs remain
decodable for old projects but are not listed as duplicate templates. `FormColumn.group_title` is
persisted and propagated to layout v10 so adjacent columns render under merged Geology,
Technology, and Gas Data section captions.

Lithology intervals and shared cuttings samples are editable after creation. A shared sample owns
its cuttings composition, LBA, calcimetry, rich description, and interpretation; an atomic update by
`sample_id` refreshes every linked track without creating duplicates.

## SKF adapter

Legacy `.skf` forms are converted at the repository boundary. Recognised Delphi controls become
columns, tracks, parameter bindings and header elements. The result is an ordinary editable user
`FormDocument` linked to an ordinary `MasterlogTemplate`; all later editing, preview and printing
uses the existing Form Engine and Masterlog renderer.

## Рабочие формы 0.7.45

Form schema v6 сохраняет не только структуру колонок, но и видимый вертикальный интервал,
`source_dataset_id`, `source_index_id` и монотонно возрастающую `revision`. Для каждой кривой
сохраняются отдельные `x_min/x_max`, linear/log, стиль линии, цвет названия и цвет линии под
названием. Для каждого трека отдельно сохраняются grid X/Y, major/minor divisions, alpha и
печать сетки. Глубинные комментарии, изображения и символы хранятся в проекте под стабильным
scope `dataset:{dataset_id}:form:{form_id}`; повторное применение формы возвращает тот же scope.

## Инженерная шкала и единица кривой

Начиная с 0.7.48 рабочая шапка ordinary curve использует тот же нормализованный контракт
major/minor divisions, что и сетка колонки. Minimum/maximum отображаются и редактируются по
краям, промежуточные подписи рассчитываются в linear либо logarithmic пространстве.
`unit_override` является только display-настройкой: массив значений и source metadata не
конвертируются. При сохранении пользовательской формы разрешённая единица переносится в
`ParameterBinding.unit`; при применении формы она возвращается в `CurveDisplaySettings`.
Tablet layout v16 мигрирует v15 через `unit_override = null`, поэтому старые проекты продолжают
показывать единицу исходного канала.

## Адаптивная шкала и транзакционное применение формы 0.7.49

Новые и автоматически materialized bindings используют `XScale.LINEAR`; явно сохранённый
логарифмический режим не перезаписывается. Curve render key включает raw viewport geometry,
`x_scale`, `x_min` и `x_max`, поэтому изменение пределов перестраивает положение кривой, а не
только текст ruler. Header разбит на адаптивные строки: caption/actions, minimum/maximum,
unit/scale и ruler.

Form Manager применяет layout через reversible transaction. Candidate сначала полностью
рендерится в `TabletView`, затем устанавливается через `TabletController`. При ошибке render или
commit восстанавливаются snapshot layout, dirty marker и selected track. Cancel после live preview
восстанавливает исходную форму; частично применённая форма не остаётся рабочей.
