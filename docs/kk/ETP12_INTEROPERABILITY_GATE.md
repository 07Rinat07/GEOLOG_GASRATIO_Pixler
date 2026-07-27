# ETP 1.2 interoperability gate

## Тест ортасы

Server өнімі/нұсқасы, endpoint, certificate chain, auth mode, dataspace, WITSML нұсқалары, channel және
сынақ уақыты жазылсын. Жеке read-only service account қолданылсын.

## Қауіпсіздік және handshake

- [ ] WSS certificate validation тексеруді өшірмей өтеді.
- [ ] WebSocket subprotocol дәл `etp12.energistics.org`.
- [ ] Password/token project, profile JSON, audit және screenshot ішінде жоқ.
- [ ] RequestSession үшін бір дұрыс OpenSession алынды.
- [ ] Core, Discovery, Store, Data Array және Channel Subscribe role келісілді.
- [ ] Unsupported protocol басқарылатын диагностика береді.

## Protocol behavior

- [ ] Әр request/response correlation ID дұрыс.
- [ ] Multipart тек FIN кезінде аяқталады және реті дұрыс.
- [ ] ACK flag үшін дұрыс correlation ID бар бір Acknowledge жіберіледі.
- [ ] ProtocolException тек тиісті операцияны аяқтайды.
- [ ] Max message және endpoint capabilities сақталады.

## Деректер

- [ ] Discovery күтілген Well/Wellbore/Log/Channel resource қайтарады.
- [ ] Store WITSML 2.x XML-ді толық қайтарады.
- [ ] Data Array metadata/value тәуелсіз export-пен сәйкес.
- [ ] Channel metadata URI, ID, index kind, UOM және data kind дұрыс.
- [ ] ChannelData index/value аспап көзімен сәйкес.

## Қалпына келтіру

- [ ] Белсенді subscription кезінде network үзіледі.
- [ ] Session UI тоқтатпай FAILED/RECONNECTING күйіне өтеді.
- [ ] Bounded reconnect жаңа negotiated session ашады.
- [ ] Active subscriptions retained index-тен қалпына келеді.
- [ ] Overlap downstream deduplicate; жасырын gap жоқ.
- [ ] Operator close reconnect-ті тоқтатып, таза жабылады.

## Soak және дәлел

- [ ] Кемінде 8 сағат, 24 сағат ұсынылады.
- [ ] Message/ACK/reconnect/subscription counters және memory growth сақталады.
- [ ] Run соңында hash-chain audit тексеріледі.
- [ ] Anonymized metadata, screenshot және қол қойылған нәтиже сақталады.
- [ ] Барлық blocking тармақ өткен соң ғана field-ready белгіленеді.
