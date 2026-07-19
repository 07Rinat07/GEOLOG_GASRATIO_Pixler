# Статус проекта GEOLOG Gas Ratio & Pixler

## Текущий рабочий модуль

Tablet Engine 2.0 — Rendering Engine.

## Последнее выполненное изменение

Завершён Overlay Engine первого уровня: курсор, выделение, маркеры, аннотации, preview интервалов, tooltip и rubber-band разделены на независимые слои. Каждый слой имеет собственные видимость, Z-порядок, dirty-состояние и счётчики обновлений. Изменение overlay не перестраивает геометрию кривых и статические дорожки.

## Следующая задача

Добавить панель диагностики производительности Overlay/Geometry/Static Cache и зафиксировать рабочие бюджеты на реальных LAS под Windows. После этого перейти к Selection & Interaction Engine.


## Selection & Interaction Engine — второй срез

Реализована единая модель выделения объектов планшета: `SelectionRef`, `SelectionManager`, общий `HitResult`, выбор лучшего hit-кандидата и `CommandStack`. Дополнительно работают hit-testing заголовков и ближайшей кривой, интерактивные resize handles, перестановка дорожек drag-and-drop и Undo/Redo для изменения ширины и порядка.

## Current implementation slice

Selection & Interaction Engine now includes multi-selection, selected-curve properties in the inspector, and context operations for tracks. The next slice is the unified properties editor for editable track/curve fields and batch operations on a multi-selection.

## Form Engine: первый срез выполнен

Реализованы модель формы, колонки, дорожки и привязки параметров, схема JSON v1,
валидация, миграция, пользовательское хранилище и заводские шаблоны. Следующий фактический
срез — менеджер форм и применение выбранной формы к текущему планшету без визуального конструктора.

- Completed: visual form structure editor for user templates (column/track CRUD, ordering, widths, titles, track types, preview and JSON save).
