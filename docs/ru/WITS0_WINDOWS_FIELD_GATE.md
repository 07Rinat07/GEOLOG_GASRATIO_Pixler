# Полевой Windows reliability gate для WITS0

## Статус

Gate выполняется параллельно с разработкой WITSML на целевом Windows-компьютере, подключённом к
реальному потоку GeoScape/GSWITS. Версия 0.7.79 содержит программные средства и checklist, но не
заявляет, что физическая полевая проверка уже пройдена.

## Обязательная конфигурация

В отчёте фиксируются компьютер, Windows build, версия приложения и SHA-256, режим соединения
GSWITS, фактические IP/port, включённые записи и интервалы, raw-диск, пороги свободного места,
retention policy, источник NTP и оператор проверки. Порты на vendor screenshots являются только
примерами и не должны приниматься по умолчанию.

## Минимальный прогон

Минимум 8 часов, предпочтительно 24 часа. В прогон входят обычный поток, контролируемый restart
GSWITS, restart приложения с открытой acquisition session, сетевой разрыв и восстановление, raw
rotation, save/reopen проекта, pause/resume live-monitor и просмотр истории.

## Доказательства приёмки

Сохраняются raw-сегменты `.wits`, chunk indexes, connection journal, recovery manifest, файл
проекта, application log, JSON soak report и screenshots соединения/live-monitor. Проверяется:

- для всех принятых TCP-байтов существует raw reference;
- connection ID и причины отключения заполнены;
- replay даёт тот же parser/discovery результат, что live capture;
- acquisition sequence и checkpoints продолжаются после restart;
- disk warning/critical работают по настройке;
- retention не удаляет активный raw-файл;
- отсутствуют unhandled exception, зависание UI и устойчивый рост памяти;
- финальный recovery manifest содержит clean shutdown.

Невыполненный критерий оставляет gate открытым. В отчёте указываются timestamp ошибки,
connection ID, raw segment и исправляющая версия.
