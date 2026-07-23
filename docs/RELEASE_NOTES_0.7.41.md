# Примечания к выпуску 0.7.41 — типизированные operational events

- добавлены строгие drilling/gas/show/sample/casing/formation-top payload-модели;
- добавлен общий event envelope с depth/time anchors, source, revision, calibration и QC flags;
- реализован детерминированный QC для duplicate, out-of-order, gap, stale и calibration;
- добавлен `OperationalEventController` с optimistic revision и запретом cross-well mutation;
- project format повышен до v17; миграция v16 → v17 добавляет пустую event collection;
- codec восстанавливает payload по discriminator и отклоняет неизвестные/несогласованные поля;
- EVENTS/DRILLING подключены к точному интервалу `ResolvedReportDefinition` без повторного resolve;
- удалены устаревшие дубликаты import-controller из `ui`; рабочая граница остаётся в `services`;
- добавлены headless domain, controller, QC, migration, codec и report tests;
- обновлены план, статус, CHANGELOG и инструкции RU/KK/EN.

Сборка остаётся тестовой до полного Ruff/mypy/Qt/LAS gate и Windows smoke-test.
