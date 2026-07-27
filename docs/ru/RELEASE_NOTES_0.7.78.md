# GEOLOG GASRATIO@Pixler 0.7.78 — надёжность и восстановление WITS0

Добавлены стабильные `connection_id`, append-only JSONL-журнал подключений и типизированные
connection/disconnection records внутри открытой `AcquisitionSession`. События проходят только через
`AcquisitionController` и не создают фиктивных measurement rows.

Capture worker проверяет свободное место перед raw-записью и в idle-состоянии. Warning показывается
оператору, critical останавливает захват до принятия данных без raw-копии. Настраиваемый retention
удаляет только неактивные `.wits` и sidecar-файлы, защищая текущий сегмент.

Атомарный recovery manifest фиксирует run, соединение, raw-сегмент, acquisition session и custom
profile. После аварийного завершения исправляется только обрезанный хвост chunk-index JSONL; raw
байты не изменяются. Открытая сессия проекта возобновляется по immutable schema и versioned profile
с продолжением sequence/checkpoints.

Сохраняются axis mode, auto-follow, pause-view, follow span, rendering budget, выбранные каналы,
history range и session ID. Добавлены `tools/wits0_soak_test.py` и PowerShell-обёртка для длительной
Windows-проверки с reconnect, chunk splitting, gaps, duplicates и malformed values.

Project format остаётся v20. Реальный GSWITS soak, физический disk-full, Windows Service и signed
field checklist пока не объявляются пройденными.
