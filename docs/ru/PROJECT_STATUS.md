# Статус проекта

Срез: 24 июля 2026 года. Версия пакета: **0.7.51**, постоянная runtime-диагностика и
исправление lifecycle карандаша/форм. Project format: **v20**, form schema: **v6**, tablet
layout: **v16**.

## Завершено в 0.7.51

- приложение ведёт вращаемый `geolog.log` и отдельный `geolog-crash.log`;
- записываются необработанные Python/thread exceptions, Qt messages и ошибки Qt event handlers;
- события применения/отката форм, полного рендера планшета и curve-pencil commit имеют стабильные
  коды и traceback;
- меню «Справка» открывает папку журналов, копирует путь и создаёт diagnostics ZIP;
- diagnostics ZIP не содержит значения LAS, datasets, формы и проектные assets;
- карандаш после commit обновляет только затронутые и пересчитанные curve tracks;
- автоматические диапазоны шапки обновляются на существующих редакторах без их удаления;
- полный rebuild больше не выполняется после каждого штриха, поэтому форма, ширины колонок и
  горизонтальная позиция сохраняются;
- перед form rebuild карандаш выключается, preview очищается, stale track/curve targets удаляются;
- candidate form сначала проверяется, затем выполняется безопасное прекращение pencil mode;
- ошибки apply/rollback записываются в журнал, а восстановление по-прежнему строится из модели.

## Проверка

- focused logging/form/pencil/tablet suite: **245 passed**;
- доступная headless-регрессия: **1048 passed, 4 skipped, 4 deselected**;
- `compileall` выполнен;
- Windows smoke-test с PySide6 остаётся обязательным: реальное рисование, Undo/Redo, изменение
  форм сразу после штриха и создание diagnostics ZIP.

## Следующий вертикальный срез

Read-only offline WITSML 2.1 inventory и mapping fixtures. ETP 1.2 остаётся заблокирован до
fixture replay.
