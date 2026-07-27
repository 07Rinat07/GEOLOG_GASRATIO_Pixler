# GEOLOG GASRATIO@Pixler 0.7.81 — основа клиента WITSML 2.x / ETP 1.2

## Защищённая WebSocket-сессия

Добавлен Qt-независимый клиент ETP v1.2 поверх бинарных WebSocket-сообщений. Production adapter
запрашивает subprotocol `etp12.energistics.org`, требует `wss://` для удалённых узлов, по умолчанию
проверяет TLS, ограничивает размер сообщения и задаёт ping/open/close timeout. Незашифрованный
`ws://` разрешён только для явно включённого localhost-теста. Credentials внутри URL запрещены.

## Сессия и согласование протоколов

`RequestSession` объявляет ETP 1.2 Core, Channel Streaming, Discovery, Store, Data Array и Channel
Subscribe, а также семейства WITSML 2.0/2.1 и EML. Ответ `OpenSession` проверяется до открытия
прикладных операций. Отсутствующий протокол блокируется на границе сервиса с точной диагностикой.

## Correlation, multipart и acknowledgement

Клиент использует чётные последовательные message ID. Ожидающие запросы индексируются по message ID,
части ответа связываются по correlation ID и накапливаются до FIN, после чего сортируются по message
ID. На серверный ACK-флаг автоматически отправляется Core Acknowledge с correlation ID исходного
серверного сообщения. ProtocolException завершает соответствующий запрос типизированной ошибкой.

## Discovery, Store и Data Array

Read-only facade поддерживает Discovery `GetResources`, Store `GetDataObjects`, metadata Data Array
и чтение Data Array. Resources, data objects, identifiers, dimensions и values преобразуются в
immutable модели приложения. Методы записи, удаления и транзакций ETP наружу не предоставляются.

## Channel Streaming и Channel Subscribe

Клиент принимает unsolicited ChannelData как от простого Channel Streaming, так и от Channel
Subscribe. Для восстанавливаемых подписок Store запрашивается metadata каналов, URI связываются с
числовыми channel ID, подписка начинается с заданного или последнего индекса, а данные выдаются как
immutable channel batches.

## Reconnect и восстановление подписок

Watchdog обнаруживает завершение receive loop, выполняет ограниченные экспоненциальные reconnect,
повторяет negotiation и восстанавливает все незакрытые подписки. Продолжение начинается с наибольшего
сохранённого channel index; возможное перекрытие устраняет downstream acquisition. Состояния и
поколения подписок доступны в immutable snapshot.

## Credentials и аудит

Публичный JSON-профиль не содержит пароль или bearer token. В Windows используется отдельный
Credential Manager namespace `GEOLOG_GASRATIO_Pixler/ETP12/`; в других системах секреты хранятся
только в памяти процесса. Append-only JSONL-аудит связан SHA-256, очищает endpoint и не сохраняет
payload или Authorization.

## Интеграция интерфейса

Добавлен пункт **Файл → WITSML 2.x / ETP 1.2…**. Постоянный QThread владеет asyncio loop и
WebSocket-сессией, поэтому network/Avro работа не выполняется в GUI thread. Диалог содержит профиль,
Discovery tree, Store preview, Data Array, channel metadata, subscribe/unsubscribe, текущие значения
и протокольные метрики.

## Проверки и ограничения

Headless gate проверяет correlation, multipart FIN, ACK, audit, защищённые профили, Discovery, Store,
Data Array, ручной и автоматический reconnect и восстановление подписок. Generated runtime
`etptypes`/`etpproto` недоступен во внутреннем package index контейнера, поэтому реальная Avro wire
совместимость здесь не проверена. PySide6/pyqtgraph также отсутствуют; полный Qt runtime-suite не
выполнялся. До полевого применения обязателен тест с реальным ETP 1.2 server.

Project format остаётся v20, form schema v8, tablet layout v18. Контракты компактных колонок и
библиотеки форм готовы и не изменены: 50%, 48, 80, пользовательские формы, защита от совпадений и
пробелов, все готовые формы остаются видимыми через «Создать форму» и «Сохранить пользовательскую форму».
