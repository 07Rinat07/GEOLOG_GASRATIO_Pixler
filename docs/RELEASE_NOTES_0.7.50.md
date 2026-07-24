# GEOLOG GASRATIO@Pixler 0.7.50 — безопасное переключение форм

Исправлена критическая ошибка PySide6 `Internal C++ object (CurveHeaderEditor) already deleted`,
которая могла возникнуть после редактирования шкалы и переключения рабочей формы.

## Изменения

- `CurveHeaderEditor.dispose()` останавливает отложенный range commit до удаления виджета;
- minimum/maximum, unit, scale и action-кнопки блокируют сигналы при disposal;
- `TabletTrackWidget` гасит редакторы и event filters до `deleteLater`;
- `TabletView` имеет rebuild guard, исключающий вложенное перестроение;
- MainWindow игнорирует stale header events во время form transaction;
- rollback строит предыдущее состояние из fresh deepcopy модели, а не из старых Qt-объектов;
- Form Manager больше не выполняет двойное восстановление после одной ошибки;
- при Cancel после preview исходная форма восстанавливается отдельно и один раз.

## Совместимость

Package **0.7.50**; project format **v20**; form schema **v6**; tablet layout **v16**.
Миграция не требуется.

## Проверка

Focused lifecycle/form/layout: **171 passed**. Доступная headless-регрессия:
**1044 passed, 4 skipped, 4 deselected**. `compileall` выполнен. Реальный Qt lifecycle
требует финального Windows/PySide6 smoke-test.
