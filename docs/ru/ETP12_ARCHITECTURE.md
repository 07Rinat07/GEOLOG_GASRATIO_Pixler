# Архитектура ETP 1.2

## Граница подсистемы

ETP разделён на generated-model transport, протокольный state machine, read-only application facade и
Qt worker. ETP-зависимости не импортируются при обычном импорте пакета; generated runtime загружается
только при запуске реальной WebSocket-сессии.

## Компоненты

- `models.py`: immutable профили, negotiated protocols, resources, arrays, channel batches, subscriptions
  и snapshots.
- `etpproto_adapter.py`: WebSocket/TLS/auth и Avro encode/decode.
- `protocol.py`: message IDs, correlation, multipart FIN, ACK, timeout и unsolicited dispatch.
- `service.py`: проверка negotiation, Discovery, Store, Data Array, Channel Subscribe, watchdog и restore.
- `etp12_profiles.py`, `etp12_credentials.py`, `etp12_audit.py`: настройки, секреты и аудит.
- `etp12_dialog.py`: постоянный QThread с asyncio и интерфейс оператора.

## State machine

```text
DISCONNECTED → CONNECTING → NEGOTIATING → OPEN
      ↑                                  ↓
      └──── RECONNECTING ← FAILED ← ошибка receive loop

OPEN → CLOSING → CLOSED
```

Receive loop является источником состояния соединения. При ошибке он переводит engine в FAILED и
разблокирует pending requests. Watchdog создаёт новый engine, повторяет negotiation и восстанавливает
подписки. Штатное закрытие сначала отменяет watchdog, затем закрывает WebSocket.

## Контракт сообщений

Клиентские message ID чётные. У запроса correlation ID равен нулю. Ответ и multipart parts ссылаются
на ID исходного запроса. Request завершается только после FIN; части возвращаются по message ID.
ACK обрабатывается отдельно и не попадает в прикладной список ответов.

Каждый профиль подключения независимо ограничивает одно WebSocket-сообщение, суммарный encoded-объём
multipart-ответа, число частей и время от первой незавершённой части до FIN. Значения по умолчанию:
16 МиБ на сообщение, 64 МиБ на multipart, 256 частей и 30 секунд. Adapter перед декодированием
передаёт фактический размер binary frame; превышение лимита завершает pending requests и закрывает
сессию, поэтому поздние части не могут быть ошибочно обработаны как unsolicited traffic.

## Read-only policy

Наружу доступны только Discovery, Store retrieval, Data Array retrieval, channel metadata и channel
subscription. Facade для Put/Delete/Transaction/DataLoad отсутствует. Это программная safety boundary,
а не только скрытая кнопка интерфейса.

## Безопасность

Для удалённых endpoint требуется WSS и проверенный сертификат. Basic/Bearer secrets загружаются из
credential store и не попадают в проект. Profile и audit очищаются; аудит содержит metadata,
message/correlation IDs, timing и outcome, но не Avro payload.

## Восстановление подписок

Subscription хранит immutable definition, server channel IDs, generation и последний index каждого
канала. Reconnect переводит её в RESTORING и подписывается с последнего индекса. Сервер может вернуть
overlap; deduplication выполняется downstream acquisition с сохранением provenance.

## Оставшаяся interoperability-проверка

Нужна матрица реальных server: endpoint capabilities, auth, multipart/chunk, ChannelData union types,
URI dialect и reconnect overlap. Сейчас streaming batches отображаются и доступны callback; создание
отдельной append-only ETP acquisition session остаётся следующим интеграционным срезом.
