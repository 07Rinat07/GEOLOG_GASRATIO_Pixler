# ETP 1.2 архитектурасы

## Ішкі шекара

ETP generated-model transport, protocol state machine, read-only facade және Qt worker болып бөлінді.
Пакет жай импортталғанда ETP dependency жүктелмейді; generated runtime нақты WebSocket сессиясы
ашылғанда ғана lazy import арқылы қосылады.

## Компоненттер

- `models.py`: immutable profile, negotiated protocol, resource, array, channel batch және snapshot.
- `etpproto_adapter.py`: WebSocket/TLS/auth және Avro encode/decode.
- `protocol.py`: message ID, correlation, multipart FIN, ACK, timeout және unsolicited dispatch.
- `service.py`: negotiation, Discovery, Store, Data Array, Channel Subscribe, watchdog және restore.
- profile/credential/audit services: public settings, secret және audit.
- `etp12_dialog.py`: тұрақты QThread, asyncio loop және оператор интерфейсі.

## State machine

```text
DISCONNECTED → CONNECTING → NEGOTIATING → OPEN
      ↑                                  ↓
      └──── RECONNECTING ← FAILED ← receive loop қатесі

OPEN → CLOSING → CLOSED
```

Receive loop connection failure үшін негізгі authority. Қате кезінде engine FAILED күйіне өтеді және
pending request босатылады. Watchdog жаңа engine жасап, negotiation қайталап, subscription restore
етеді. Қалыпты close алдымен watchdog-ты тоқтатады.

## Хабар келісімі

Client message ID жұп. Request correlation ID нөл. Response және multipart parts бастапқы request ID-ге
сілтейді. Request тек FIN келгенде аяқталады және бөліктер message ID бойынша қайтарылады. ACK бөлек
өңделеді және application response тізіміне кірмейді.

Әр connection profile бір WebSocket message өлшемін, multipart response жалпы encoded көлемін,
бөліктер санын және бірінші аяқталмаған бөліктен FIN-ге дейінгі уақытты бөлек шектейді. Әдепкі
мәндер: message үшін 16 MiB, multipart үшін 64 MiB, 256 бөлік және 30 секунд. Adapter decode алдында
binary frame нақты өлшемін береді; лимит асса pending requests аяқталып, session жабылады, сондықтан
кеш келген бөліктер unsolicited traffic ретінде өңделмейді.

## Read-only policy

Тек Discovery, Store retrieval, Data Array retrieval, channel metadata және subscription ашық. Put,
Delete, Transaction және DataLoad facade жоқ. Бұл UI шектеуі емес, application safety boundary.

## Қауіпсіздік

Remote endpoint үшін WSS және certificate verification талап етіледі. Basic/Bearer secret credential
store арқылы алынады және project файлына түспейді. Audit protocol metadata мен timing сақтайды, бірақ
Avro payload немесе Authorization сақтамайды.

## Subscription recovery

Әр subscription immutable definition, server channel ID, generation және соңғы index сақтайды.
Reconnect кезінде RESTORING күйіне өтіп, соңғы индекстен қайта жазылады. Server overlap жіберуі мүмкін;
deduplication downstream acquisition ішінде provenance сақтала отырып орындалады.

## Қалған interoperability жұмысы

Нақты server matrix endpoint capabilities, auth, multipart/chunk, ChannelData union, URI dialect және
reconnect overlap тексеруі тиіс. Қазір streaming batch UI мен callback-қа беріледі; append-only ETP
acquisition session келесі integration slice болады.
