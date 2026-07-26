# GEOLOG GASRATIO@Pixler 0.7.73 — WITS0 raw-захват и офлайн-инвентарь WITSML 2.x

## WITS Level 0

- Добавлена команда **«Файл → Захват WITS Level 0...»** с модельным окном, которое не блокирует
  работу с основным интерфейсом.
- Поддерживаются оба режима GSWITS: Pixler как TCP-сервер и Pixler как TCP-клиент.
- TCP-клиент автоматически переподключается с ограниченной увеличивающейся задержкой.
- Сетевой worker изолирован от Qt GUI; `accept`, `connect` и `recv` не выполняются в UI-потоке.
- Исходные байты сохраняются раньше разбора в append-only `*.wits`-сегменты.
- Для каждого TCP chunk записывается `*.chunks.jsonl` с UTC arrival time, offset, size и
  connection ID.
- Incremental frame decoder корректно обрабатывает произвольные границы TCP chunks и выделяет
  пакеты `&& ... !!`.
- Live-поток и replay raw-файла используют один decoder.
- Добавлен строгий GeoScape GSWITS profile schema v1: 11 records и 105 fields из руководства
  GSWITS. Профиль является исходной гипотезой и требует подтверждения реальным raw-дампом.

## WITSML 2.x

- Добавлен безопасный read-only inventory отдельных XML/WITSML-файлов, каталогов и ZIP/EPC.
- Отображаются top-level objects, version, UUID, references и Channel metadata/indexes.
- Архивы не извлекаются на диск; unsafe paths, DTD/entities, encryption, duplicate paths и
  resource-limit violations отклоняются.

## Ограничения

- WITS0 пока не разбирается в `record/item/value` и не создаёт `Dataset` или
  `AcquisitionSession`.
- Встроенный GSWITS mapping нельзя считать подтверждённым без реального потока конкретной
  установки.
- WITSML inventory пока не читает channel arrays и не подключается по SOAP/ETP.
- WITS0 raw-файлы являются отдельными artifacts и не заменяют сохранение проекта через
  **Ctrl+S**.

Project format остаётся `v20`, form schema — `v8`, tablet layout — `v18`.
