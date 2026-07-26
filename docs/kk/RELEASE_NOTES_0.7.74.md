# GEOLOG GASRATIO@Pixler 0.7.74 — WITS0 raw-қабылдау және WITSML 2.x офлайн түгендеуі

## WITS0 parser және sequence diagnostics

- Immutable `Wits0ParsedFrame`/`Wits0ParsedField` нәтижелері бар headless `Wits0Parser` қосылды.
- Өрістер `float`, `integer`, `text`, `date` немесе `time` ретінде типтеледі; бастапқы жол және raw value сақталады.
- Unknown record/item, duplicate field, malformed line/value, бос мән және NaN/Inf диагностикаланады.
- `Wits0SequenceTracker` әр record реттілігін бөлек бақылап, first, contiguous, duplicate, gap және out-of-order күйін көрсетеді.
- Live TCP және replay бір `Wits0StreamProcessor` қолданады; әртүрлі TCP chunk boundaries кезінде нәтиже теңдігі тестпен дәлелденді.
- Қабылдау терезесіне талданған өрістер, parser counters және sequence anomalies қосылды.
- Dataset commit, UOM conversion және Import Review келесі кезеңде орындалады.


## WITS Level 0

- Негізгі жұмыс аймағын бұғаттамайтын модельсіз **Файл → WITS Level 0 қабылдау...** терезесі
  қосылды.
- GSWITS екі режимі қолдау табады: Pixler TCP сервері және Pixler TCP клиенті ретінде.
- TCP клиенті шектелген өсетін кідіріспен автоматты түрде қайта қосылады.
- Желілік worker Qt GUI-ден оқшауланған; `accept`, `connect` және `recv` UI ағынында орындалмайды.
- Бастапқы байттар parser алдында append-only `*.wits` сегменттеріне сақталады.
- Әр TCP chunk үшін UTC arrival time, offset, size және connection ID бар `*.chunks.jsonl`
  жазбасы жасалады.
- Incremental frame decoder TCP chunk шекараларына тәуелсіз толық `&& ... !!` frames бөледі.
- Live capture және raw-file replay бір decoder қолданады.
- GSWITS нұсқаулығынан 11 records және 105 fields енгізілген қатаң GeoScape GSWITS profile
  schema v1 қосылды. Нақты raw арқылы расталғанға дейін бұл бастапқы гипотеза болып қалады.

## WITSML 2.x

- XML/WITSML файлдарын, каталогтарды және ZIP/EPC пакеттерін қауіпсіз read-only түгендеу қосылды.
- Top-level objects, version, UUID, references және Channel metadata/indexes көрсетіледі.
- Архивтер дискіге шығарылмайды; unsafe paths, DTD/entities, encryption, duplicate paths және
  resource-limit violations қабылданбайды.

## Шектеулер

- WITS0 `record/item/value` түрінде талданады, бірақ UOM mapping әзірше орындалмайды және
  `Dataset` немесе `AcquisitionSession` жасалмайды.
- Кіріктірілген GSWITS mapping нақты орнату үшін real capture жоқ кезде дәлелденген емес.
- WITSML inventory channel arrays оқымайды және SOAP/ETP арқылы қосылмайды.
- WITS0 raw-файлдары жеке artifacts болып табылады және жобаны **Ctrl+S** арқылы сақтауды
  алмастырмайды.

Project format `v20`, form schema `v8`, tablet layout `v18` болып қалады.
