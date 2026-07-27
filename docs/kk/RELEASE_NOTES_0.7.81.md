# GEOLOG GASRATIO@Pixler 0.7.81 — WITSML 2.x / ETP 1.2 клиентінің негізі

## Қорғалған WebSocket сессиясы

Бинарлық WebSocket хабарлары арқылы Qt-ға тәуелсіз ETP v1.2 клиенті қосылды. Production adapter
`etp12.energistics.org` subprotocol сұрайды, қашықтағы сервер үшін `wss://` талап етеді, TLS-ті
әдепкі бойынша тексереді, хабар өлшемін шектейді және ping/open/close timeout орнатады. Шифрланбаған
`ws://` тек арнайы рұқсат берілген localhost тестіне арналған. URL ішіндегі credentials қабылданбайды.

## Сессия және протоколдарды келісу

`RequestSession` ETP 1.2 Core, Channel Streaming, Discovery, Store, Data Array және Channel Subscribe,
сондай-ақ WITSML 2.0/2.1 пен EML объектілерін жариялайды. `OpenSession` қолданбалы операциялар ашылғанға
дейін тексеріледі. Келісілмеген протокол сервис шекарасында нақты диагностикамен тоқтатылады.

## Correlation, multipart және acknowledgement

Клиент жұп және ретімен өсетін message ID қолданады. Күтудегі сұраулар message ID бойынша тіркеледі,
жауап бөліктері correlation ID арқылы біріктіріліп, FIN келгенше жиналады және message ID бойынша
сұрыпталады. ACK жалаушасы бар сервер хабарына бастапқы message ID-ге байланыстырылған Core
Acknowledge автоматты түрде жіберіледі. ProtocolException тиісті сұрауды типтелген қатемен аяқтайды.

## Discovery, Store және Data Array

Read-only facade Discovery `GetResources`, Store `GetDataObjects`, Data Array metadata және Data Array
мәндерін оқуды қолдайды. Resources, objects, identifiers, dimensions және values immutable ішкі
модельдерге түрленеді. ETP жазу, жою немесе transaction әдістері жарияланбайды.

## Channel Streaming және Channel Subscribe

Клиент қарапайым Channel Streaming және Channel Subscribe арқылы келген unsolicited ChannelData-ны
қабылдайды. Қалпына келетін Store жазылымында channel metadata сұралады, URI сандық channel ID-мен
байланысады, жазылым берілген не соңғы индекстен басталады және immutable channel batch таратылады.

## Reconnect және жазылымдарды қалпына келтіру

Watchdog receive loop істен шыққанын анықтап, шектелген экспоненциалды reconnect жасайды, negotiation
қайталайды және жабылмаған жазылымдарды қалпына келтіреді. Жалғастыру ең үлкен сақталған channel
index-тен басталады; overlap downstream acquisition арқылы deduplicate етіледі. Жазылым күйі мен
буыны immutable snapshot ішінде көрінеді.

## Credentials және аудит

Public JSON профиль пароль немесе bearer token сақтамайды. Windows-та жеке Credential Manager
namespace `GEOLOG_GASRATIO_Pixler/ETP12/` қолданылады; басқа жүйелерде secret тек процесс жадында
болады. Append-only JSONL аудиті SHA-256 тізбегімен қорғалған және payload пен Authorization сақтамайды.

## Интерфейс интеграциясы

**Файл → WITSML 2.x / ETP 1.2…** тармағы қосылды. Тұрақты QThread asyncio loop пен WebSocket
сессиясын басқарады, сондықтан network/Avro жұмысы GUI thread ішінде орындалмайды. Диалогта профиль,
Discovery tree, Store preview, Data Array, channel metadata, subscribe/unsubscribe, ағымдағы мәндер
және метрикалар бар.

## Тексеру және шектеулер

Headless gate correlation, multipart FIN, ACK, audit, қауіпсіз профильдер, Discovery, Store, Data
Array, қолмен және автоматты reconnect пен жазылымды қалпына келтіруді тексереді. Контейнер package
index ішінде generated `etptypes`/`etpproto` runtime болмағандықтан нақты Avro wire сәйкестігі мұнда
тексерілмеді. PySide6/pyqtgraph та жоқ, толық Qt runtime-suite орындалмады. Өндірістік қолдануға дейін
нақты ETP 1.2 server сынағы міндетті.

Project format v20, form schema v8 және tablet layout v18 болып қалады. Compact column және form
library келісімдері дайын: 50%, 48, 80, пайдаланушы пішіндері, қайталанатын атау мен бос орыннан
қорғау өзгермеді; «Пішін жасау» және «Пайдаланушы пішінін сақтау» арқылы барлық дайын үлгілер көрінеді.
