# HOTFIX 0.7.89 — `NoneType.role` при применении форм GeoScape2

## Подтверждение по диагностике

В `GEOLOG_diagnostics_20260727-213119.zip` зарегистрированы:

- `python.uncaught` при `open_gs2()`;
- четыре `forms.apply.failed`;
- четыре `forms.rollback.failed`;
- четыре `forms.apply.rollback_failed`.

Все трассировки ведут к
`TabletView._prefer_calendar_time_axis_for_geoscape()` и обращению к
`requested.role`, когда `requested` равен `None`.

## Корневая причина

Текущий layout сохранял `vertical_index_id` предыдущего dataset. После импорта
нового GS2-набора этот ID отсутствовал в `dataset.indexes`. Метод выполнялся до
привязки layout выбранной формы, поэтому применял старый идентификатор и падал.

## Реализация исправления

Добавлен модуль `geoworkbench.tablet.axis_selection` с детерминированным
разрешением оси:

1. существующий запрошенный DEPTH/TIME индекс;
2. активный DEPTH/TIME индекс dataset;
3. первый доступный DEPTH/TIME индекс;
4. отсутствие оси без исключения.

Для абсолютных GeoScape2/Paradox временных данных относительный TIME заменяется
на DATETIME с той же длиной массива и максимальной уверенностью. DEPTH не
заменяется.

В `set_layout_and_dataset()` порядок изменён на:

1. установка dataset;
2. привязка layout формы;
3. согласование вертикальной оси;
4. отрисовка.

## Проверка

Добавлено 7 регрессионных тестов:

- устаревший ID другого dataset;
- fallback при активном DATETIME;
- fallback при активном относительном TIME;
- миграция TIME → DATETIME;
- сохранение DEPTH;
- отсутствие миграции для не-абсолютного источника;
- контроль порядка привязки layout.
