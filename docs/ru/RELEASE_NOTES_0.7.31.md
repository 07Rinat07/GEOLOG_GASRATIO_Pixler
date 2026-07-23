# Примечания к выпуску 0.7.31 — граница изменения модели проекта

## Что изменено

- изменения сериализуемого layout планшета проходят через `TabletLayoutMutationController` и
  `TabletController`, а не через прямые присваивания в Qt-виджете;
- resize/reorder треков, вертикальный индекс и видимый диапазон сохраняют прежние жесты и
  Undo/Redo, но commit выполняется за controller boundary;
- `MainWindow` больше не меняет `session.dirty`, project collections и текущий layout напрямую;
- `DerivedDatasetController` создаёт checkpoint перед merge/external-LAS copy и выполняет
  безопасный rollback при отменённом или ошибочном экспорте;
- rollback удаляет временный dataset и его layout/source/import-report sidecars, восстанавливает
  исходные well/dataset selection и `dirty`;
- имя результата merge проверяется до регистрации dataset;
- image assets шапки Masterlog валидируются и устанавливаются одним атомарным controller-вызовом;
- session registry теперь перепривязывает 27 контроллеров;
- добавлены headless/regression/source-integrity тесты архитектурной границы.

## Совместимость

Формат проекта 15, формат layout 14 и пользовательский сценарий не изменены. Исходные LAS не
перезаписываются; изменился только владелец commit/rollback.

## Проверка

714 доступных тестов пройдено, 4 платформенных сценария пропущено; `compileall` и wheel 0.7.31
завершены без ошибок. Полный Qt/LAS pytest, Ruff, mypy и Windows/HiDPI/PDF/physical-print gate
нужно повторить в установленном окружении.
