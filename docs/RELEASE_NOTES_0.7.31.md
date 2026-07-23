# Примечания к выпуску 0.7.31 — граница изменения модели проекта

## Что изменено

- сериализуемые изменения планшета вынесены из прямых Qt-операций в
  `TabletLayoutMutationController` и `TabletController`;
- resize/reorder треков, вертикальный индекс и видимый диапазон отправляют request до изменения
  общей layout-модели, сохраняя прежние Undo/Redo и standalone-сценарии;
- `MainWindow` больше не изменяет `session.dirty`, project collections или текущий layout напрямую;
- создан `DerivedDatasetController` с checkpoint/rollback для merge и external-LAS copy;
- отменённый export удаляет временный dataset и связанные layout/source/import-report данные,
  затем восстанавливает исходные well/dataset selection и `dirty`;
- имя merged dataset валидируется контроллером до регистрации результата;
- image assets шапки Masterlog устанавливаются атомарным batch-вызовом через controller;
- session registry расширен до 27 контроллеров;
- добавлены headless, regression и source-integrity тесты, запрещающие возврат прямой мутации.

## Совместимость

Формат проекта 15, формат layout 14 и пользовательские команды не изменены. Исходные LAS не
перезаписываются. Изменён только владелец commit/rollback операций.

## Проверка

Доступная headless-регрессия: 714 тестов пройдено, 4 платформенных сценария пропущено;
`compileall` и wheel 0.7.31 завершены без ошибок. Полный Qt/LAS pytest, Ruff, mypy и ручной
Windows/HiDPI/PDF/physical-print gate нужно повторить в установленном окружении.
