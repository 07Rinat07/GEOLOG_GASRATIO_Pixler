# Interoperability gate ETP 1.2

## Тестовая среда

Зафиксировать продукт/версию server, endpoint, certificate chain, auth mode, dataspace, версии WITSML,
выбранные каналы и время теста. Использовать отдельную read-only учётную запись.

## Безопасность и handshake

- [ ] WSS certificate validation проходит без отключения проверки.
- [ ] WebSocket subprotocol точно равен `etp12.energistics.org`.
- [ ] Пароль/token отсутствует в проекте, profile JSON, audit и screenshots.
- [ ] На RequestSession получен один корректный OpenSession.
- [ ] Роли Core, Discovery, Store, Data Array и Channel Subscribe согласованы.
- [ ] Неподдерживаемый protocol выдаёт контролируемую диагностику.

## Протокольное поведение

- [ ] Correlation IDs корректны для каждого request/response.
- [ ] Multipart завершается только по FIN и части упорядочены.
- [ ] На ACK flag отправляется один Acknowledge с правильным correlation ID.
- [ ] ProtocolException завершает только связанный запрос.
- [ ] Соблюдаются max message и endpoint capabilities.

## Доступ к данным

- [ ] Discovery возвращает ожидаемые Well/Wellbore/Log/Channel resources.
- [ ] Store возвращает валидный WITSML 2.x XML без обрезки.
- [ ] Data Array metadata/values совпадают с независимым экспортом.
- [ ] Channel metadata содержит правильные URI, ID, index kind, UOM и data kind.
- [ ] ChannelData index/value совпадают с источником приборов.

## Восстановление

- [ ] Принудительно разорвать сеть при активной подписке.
- [ ] Сессия переходит FAILED/RECONNECTING без зависания UI.
- [ ] Bounded reconnect создаёт новую negotiated session.
- [ ] Все active subscription восстановлены с retained indexes.
- [ ] Overlap deduplicate downstream; скрытый gap отсутствует.
- [ ] Operator close прекращает reconnect и завершается чисто.

## Soak и доказательства

- [ ] Минимум 8 часов, рекомендуется 24 часа.
- [ ] Сохранить message/ACK/reconnect/subscription counters и memory growth.
- [ ] Проверить hash-chain audit после прогона.
- [ ] Сохранить обезличенную metadata, screenshots и подписанный результат.
- [ ] Разрешить field use только после прохождения всех blocking пунктов.
