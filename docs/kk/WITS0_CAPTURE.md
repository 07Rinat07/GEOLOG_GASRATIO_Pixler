# WITS Level 0 қабылдау және талдау

## GeoScape GSWITS стандартты тақырыбы

GeoSensor `WITS.csv` каталогы мынаны растайды: `01` Well Identifier, `02` Sidetrack/Hole Section,
`03` Record Identifier, `04` Sequence Identifier, `05` Date, `06` Time, `07` Activity Code.
Sequence QC item `04` мәнін қолданады; item `02` sequence number емес.

## Мақсаты

**Файл → WITS Level 0 қабылдау...** командасы GSWITS TCP ағынын қабылдайды, кіріс байттарын
өзгеріссіз сақтайды және әр толық пакетті типтелген parser арқылы өткізеді. Расталған Import
Review-дан кейін append-only `AcquisitionSession` бастауға болады; raw шекарасы мен parser
өзгермейді, ал Dataset тек `AcquisitionController` арқылы жаңартылады.

## TCP серверін баптау

Бұл режимді GSWITS **шығыс қосылым (TCP клиенті)** ретінде бапталған кезде қолданыңыз.

1. **Кіріс қосылым — TCP сервері** режимін таңдаңыз.
2. GSWITS сол компьютерде жұмыс істесе, әдепкі `127.0.0.1` адресін қалдырыңыз.
3. Басқа компьютер үшін сенімді интерфейстің нақты non-global IPv4 адресін және рұқсат етілген
   source желілерін CIDR түрінде көрсетіңіз, мысалы `192.168.10.0/24`. Global ranges және
   `0.0.0.0/0` қабылданбайды.
4. `0.0.0.0` үшін **0.0.0.0 bind-ін айқын рұқсат ету** опциясын қосыңыз.
5. Портты көрсетіп, raw каталогын таңдаңыз.
6. **Қабылдауды бастау** түймесін басып, қауіпсіздік ескертуін растаңыз. Listener тек CIDR
   allowlist ішіндегі peers қабылдайды; басқалары жабылып, `connection_rejected` ретінде жазылады.
7. GSWITS баптауларын сақтап, қосылым күйін тексеріңіз.

WITS0 ішінде кірістірілген encryption және authentication жоқ. Listener-ді интернетке ешқашан
ашпаңыз және router port forwarding баптамаңыз. Растау әр non-loopback TCP server іске қосылғанда
қажет және firewall орнын баспайды.

## TCP клиентін баптау

Бұл режимді GSWITS **кіріс қосылым (TCP сервері)** ретінде бапталған кезде қолданыңыз.

1. **Шығыс қосылым — TCP клиенті** режимін таңдаңыз.
2. GSWITS компьютерінің IP мекенжайы мен портын енгізіңіз.
3. **Қабылдауды бастау** түймесін басыңыз.
4. Қосылым үзілгенде Pixler шектелген ұлғаймалы кідіріспен қайта қосылады.

## Сақталатын деректер

Әр қосылымға жеке каталог жасалады. `*.wits` файлдары нақты кіріс байттарын сақтайды,
`*.chunks.jsonl` UTC уақытын, offset, TCP chunk өлшемін және connection ID мәнін жазады. Сегменттер
қайта жазылмайды және deterministic replay үшін жарамды.

Automatic retention тек таңдалған root ішінде жарамды path-bound
`.geoworkbench-wits0-owned.json` marker болғанда қосылады. Жаңа бос каталог автоматты белгіленеді.
Marker жоқ бос емес каталогты қабылдау үшін оператордың айқын растауы керек; бас тартқанда capture
жұмыс істей береді, бірақ retention файл жоймайды. Бұзылған немесе көшірілген marker жоюды
бұғаттайды. Бөгде файлдар retention нысаны болмайды.

## Parser жұмысы

Live TCP және replay үшін бір `Wits0StreamProcessor` қолданылады:

```text
TCP chunk / raw chunk
        ↓
Wits0FrameDecoder: && ... !!
        ↓
Wits0Parser: record/item/raw value
        ↓
профиль бойынша типтеу
        ↓
Wits0SequenceTracker
        ↓
immutable Wits0ParsedFrame + diagnostics
```

Parser `float`, `integer`, `text`, `date` және `time` түрлерін қолдайды. 01–07 стандартты header
өрістері ұңғыманы, бүйір оқпан/секцияны, record identifier, sequence number, күнді, уақытты және
жұмыс кодын сипаттайды. 08–99 items алдымен тексерілген профильмен, кейін толық
`geosensor-wits-level0.json` каталогымен салыстырылады; каталог UOM ойлап таппайды.

Бұзылған жол бүкіл пакетті жоймайды. Бастапқы жол, raw мән, белгісіз `record/item` және түрлендіру
қатесі Import Review қолданатын детерминирленген discovery snapshot ішінде қалады.

## Sequence number бақылауы

Реттілік әр record нөмірі үшін бөлек бақыланады. Күйлер:

- `first` — осы record үшін бірінші sequence;
- `contiguous` — күтілген келесі мән;
- `duplicate` — соңғы мәннің қайталануы;
- `gap` — аралық мәндер жоғалған;
- `out_of_order` — ескі мән кейін келген;
- `invalid` немесе `unavailable` — 04 өрісі бұзылған не жоқ.

Reconnect кезінде жаңа stream processor жасалады, сондықтан әр TCP қосылымының күйі бөлек. Raw
файл дәл сол pipeline арқылы қайта талдана алады.

## Бақылау терезесі

- **Соңғы пакеттер** бастапқы `&& ... !!` frames көрсетеді.
- **Талданған өрістер** record, sequence status, mnemonic, типтелген мән, өлшем бірлігі және
  диагностиканы көрсетеді.
- **Қосылымдар мен қателер** қосылу, үзілу, raw сегменттер, parser warnings және errors көрсетеді.
- Күй панелі өрістерді, parser warnings/errors және sequence anomalies санайды.

Терезе жабылғанда worker тоқтап, файлдар жабылады.

## Import Review

Пакеттер қабылданғаннан кейін **Импортты тексеру…** түймесін басыңыз. Диалог immutable snapshot-пен жұмыс істеп:

1. әр анықталған `record/item`, бастапқы mnemonic, type, UOM, статистика және мысалдарды көрсетеді;
2. Semantic Channel Dictionary арқылы semantic binding ұсынады;
3. WITS header datetime немесе сандық depth/time өрісін active index ретінде таңдауға мүмкіндік береді;
4. арнаны жасыруға, canonical mnemonic/kind, quantity class және UOM өзгертуге мүмкіндік береді;
5. non-numeric curves, үйлеспейтін quantity classes және сандық UOM conversion қажеттілігін бұғаттайды;
6. immutable `AcquisitionDatasetSchema` бір атомарлық әрекетпен жасайды;
7. кірістірілген GeoScape profile-ды өзгертпей, mapping-ті бөлек versioned JSON profile ретінде сақтайды.

Fingerprint mapping surface-ті сипаттайды, сондықтан бар өрістердің жаңа мәндері растауды жоймайды.
Жаңа `record/item`, inferred type/UOM өзгеруі немесе жаңа index source пайда болуы схеманы
**Ескірді** күйіне ауыстырып, қайта тексеруді талап етеді. **Анықтауды тазарту** тек ағымдағы
snapshot пен commit-ті тазартады; дискідегі versioned profiles сақталады.

## AcquisitionSession

Schema расталғаннан кейін ағымдағы ұңғыманы таңдап, **Сессияны бастау** түймесін басыңыз. Қолданба:

1. қабылданған frames-ті immutable normalized measurement batches түріне айналдырады;
2. records-ті bounded queue ішіне жартылай enqueue жасамай, атомдық түрде орналастырады;
3. backpressure кезінде `DRAIN_THEN_RETRY` саясатын қолданады;
4. жолдарды тек `AcquisitionController` арқылы жазады;
5. checkpoints-ті pending queue бос кезде ғана жасайды;
6. pending, applied, skipped, checkpoints және backpressure көрсетеді;
7. **Сессияны жабу** кезінде қабылдауды тоқтатып, queue-ды босатып, финалдық checkpoint жасайды.

Growing Dataset жоба ағашында бірден таңдалады. **Queue-ды жазу** барлық күтіп тұрған records-ті
қолмен қолданады. Белсенді сессия кезінде терезе жабылса, TCP worker алдымен тоқтайды, қалған
immutable events өңделеді және controlled close орындалады. Толық контракт: [WITS0_ACQUISITION.md](WITS0_ACQUISITION.md).

## Шектеулер

- GeoScape профилі GSWITS нұсқаулығына негізделген және нақты raw ағынмен тексерілуі тиіс;
- белгісіз өрістер Import Review ішінде сақталып, өңделеді, бірақ қолмен растауды талап етеді;
- сандық UOM conversion әлі орындалмайды: source және canonical UOM бір канондық бірлікке шешілуі керек;
- WITS0 портын интернетке ашуға болмайды; non-loopback server bind үшін айқын растау,
  non-global CIDR peer allowlist және firewall қажет;
- raw файлдар жобаны **Ctrl+S** арқылы сақтауды алмастырмайды.
