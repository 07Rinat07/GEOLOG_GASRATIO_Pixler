# Статус проекта

Срез: 24 июля 2026 года. Версия пакета: **0.7.50**, критическое исправление жизненного
цикла форм. Project format: **v20**, form schema: **v6**, tablet layout: **v16**.

## Завершено в 0.7.50

- `CurveHeaderEditor` имеет явный idempotent disposal-контракт;
- debounce-таймер диапазона останавливается до `deleteLater`, сигналы полей блокируются;
- каждый трек гасит header callbacks и снимает event filters до удаления Qt-дерева;
- во время перестроения планшета изменения range/unit/scale из старой шапки игнорируются;
- откат формы создаёт новое Qt-дерево только из `TabletLayout`, без повторного использования
  уничтоженных виджетов;
- Form Manager передаёт исходный snapshot в одну reversible transaction и больше не выполняет
  второй конкурирующий rollback после неудачного apply;
- отмена preview по-прежнему восстанавливает исходную форму, dirty-state и выбранный трек;
- project/form/layout schema не менялись, миграция не требуется.

## Проверка

- focused form/layout/lifecycle: **171 passed**;
- доступная headless-регрессия: **1044 passed, 4 skipped, 4 deselected**;
- `compileall` выполнен;
- Windows smoke-test с PySide6 остаётся обязательным для быстрого многократного переключения
  форм и проверки отсутствия `Internal C++ object already deleted`.

## Следующий вертикальный срез

Read-only offline WITSML 2.1 inventory и mapping fixtures. ETP 1.2 остаётся заблокирован до
fixture replay.
