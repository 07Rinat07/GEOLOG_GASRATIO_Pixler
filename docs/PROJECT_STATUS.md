# Статус проекта GEOLOG Gas Ratio & Pixler

## Текущий рабочий модуль

Tablet Engine 2.0 — Rendering Engine.

## Последнее выполненное изменение

Завершён Overlay Engine первого уровня: курсор, выделение, маркеры, аннотации, preview интервалов, tooltip и rubber-band разделены на независимые слои. Каждый слой имеет собственные видимость, Z-порядок, dirty-состояние и счётчики обновлений. Изменение overlay не перестраивает геометрию кривых и статические дорожки.

## Следующая задача

Добавить панель диагностики производительности Overlay/Geometry/Static Cache и зафиксировать рабочие бюджеты на реальных LAS под Windows. После этого перейти к Selection & Interaction Engine.


## Selection & Interaction Engine — второй срез

Реализована единая модель выделения объектов планшета: `SelectionRef`, `SelectionManager`, общий `HitResult`, выбор лучшего hit-кандидата и `CommandStack`. Дополнительно работают hit-testing заголовков и ближайшей кривой, интерактивные resize handles, перестановка дорожек drag-and-drop и Undo/Redo для изменения ширины и порядка.
