## 0.7.81 нұсқасында аяқталды: WITSML 2.x / ETP 1.2 клиент негізі

Қорғалған WSS transport, RequestSession/OpenSession negotiation, read-only Discovery, Store және Data
Array, Channel Streaming/Channel Subscribe, correlation, multipart FIN, automatic ACK және reconnect
кезінде subscription restore іске асырылды. Credentials пен audit project file-дан бөлек. Нақты ETP
server Avro interoperability және Windows Qt acceptance ашық қалады.


## 0.7.80 ішінде аяқталды: WITSML 1.4.1.1 SOAP тек оқу

GetVersion, GetCap және read-only GetFromStore, Well → Wellbore → Log → LogData навигациясы,
timeout, bounded retry, hash-chained audit және Windows Credential Manager құпиясөз сақтау қосылды.
Remote LogData қолданыстағы Import Review және атомарлық Dataset тіркеуін пайдаланады. Add, Update
және Delete клиент шекарасында тыйым салынған.
# Жоба күйі

## Әзірленуде: WITS0 далалық қабылдауы

Raw capture, parser, Import Review, append-only acquisition, live monitor және reliability software
кезеңдері орындалды. Connection records, disk guard, raw retention, restart recovery, workspace
persistence және Windows soak tooling дайын. Нақты 8–24 сағаттық GSWITS soak, бақыланатын
low-space/disk-full сынағы, independent channel scales, Windows startup/service бағалауы және signed
field checklist қалды. GeoScape mapping нақты anonymized ағынмен расталуы тиіс.

## 0.7.79 ішінде аяқталды: WITSML 2.x офлайн импорты

Қауіпсіз inventory енді embedded/relative-file `ChannelData` оқиды, ChannelSet, белсенді time/depth
index және scalar numeric channel таңдауға мүмкіндік береді. Import Review semantic mapping,
қатаң UOM conversion және row QC орындайды, содан кейін source/data SHA-256 және тұрақты digest бар
Dataset-ті атомарлық құрады. Binary Avro, multidimensional arrays, SOAP және ETP кейінгі жұмыс.

## Әзірленуде: GeoScape II GS2

Контейнерді қауіпсіз тексеру және таңдалған ішкі кестені қолданыстағы Paradox reader, Import
Review және `Dataset` арқылы импорттау қосылды. СГ-8 үлгісінде 13 Paradox 7.x кестесі танылды;
`GS2#101.db` ішінде TIME, DEPTH және 0,2 м торындағы 206 арна бар. `GS2#1…GS2#1_4` бес бөлігі
4 338 103 жолдық тексерілген TIME сериясына автоматты біріктіріледі. `GS2.mdb` read-only Qt
ODBC/ACE арқылы оқылады: `WELLS`, `FORMULAS.RESGID → S-код`, Sensors fallback және аудит
қосылады. Драйвер жоқ болса да кесте импорты тоқтамайды және нақты диагностика көрсетіледі.



## 0.7.78 нұсқасында аяқталды

Stable connection IDs, append-only fsync lifecycle journal, типтелген connection acquisition
records, pre-write disk guard, inactive raw retention, atomic recovery manifest, sidecar repair,
ашық сессияны restart recovery, per-well workspace persistence және Python/PowerShell Windows soak
құралдары қосылды. Project format v20 болып қалды.

## 0.7.77 нұсқасында аяқталды

Growing Dataset үстінде current values, time/depth axes, auto-follow, pause-view,
history/downsampling және source/axis/invalid/missing markers бар read-only live projection қосылды.

## 0.7.76 нұсқасында аяқталды

`Wits0FrameNormalizer`, immutable normalized measurement batches және
`Wits0AcquisitionRuntime` қосылды. Расталған frames атомдық bounded enqueue, backpressure policy,
checkpoints және controlled close арқылы append-only `AcquisitionSession` ішіне түседі. WITS0
терезесі ағымдағы ұңғыма үшін сессия бастайды, pending/applied/skipped counters көрсетеді және
growing Dataset таңдайды. Live/replay batches детерминирленген; жабық сессия project format
өзгермей save/reopen тексеруінен өтеді.

Күй күні: 27 шілде 2026 жыл. Пакет нұсқасы: **0.7.76**. Project format: **v20**, form schema: **v8**, tablet layout: **v18**.

## 0.7.75 нұсқасында аяқталды

WITS0 Import Review қосылды: immutable discovery snapshot, барлық анықталған record/item,
Semantic Channel Dictionary сәйкестігі, бастапқы және канондық UOM, time/depth index таңдау,
hide/rename/manual override, versioned custom profile және immutable
`AcquisitionDatasetSchema` атомарлық commit. Жаңа немесе өзгерген record/item raw/parser
деректерін өзгертпей, расталған схеманы ескірген күйге ауыстырады.

Күй күні: 27 шілде 2026 жыл. Пакет нұсқасы: **0.7.75**. Project format: **v20**, form schema: **v8**, tablet layout: **v18**.

## 0.7.74 нұсқасында аяқталды

Типтелген WITS0 parser, immutable parsed models, diagnostics және әр record үшін sequence tracking
қосылды. Live TCP және replay бір pipeline қолданады; қабылдау терезесі parsed fields және
anomalies көрсетеді. Dataset commit келесі кезең болып қалады.

Күй күні: 27 шілде 2026 жыл. Пакет нұсқасы: **0.7.74**. Project format: **v20**, form schema: **v8**, tablet layout: **v18**.

## 0.7.73 нұсқасында аяқталды

Qt-тәуелсіз WITS0 source adapter және модельсіз **WITS Level 0 қабылдау** терезесі қосылды.
Желілік worker GUI-ді бұғаттамайды; raw bytes framing алдында сақталады және UI queue қысымы raw
деректерін жоғалтпайды. TCP chunks UTC/offset/size арқылы индекстеледі, live/replay бір decoder
қолданады. Dataset әзірше жасалмайды.

Күй күні: 27 шілде 2026 жыл. Пакет нұсқасы: **0.7.73**. Project format: **v20**, form schema: **v8**, tablet layout: **v18**.

## 0.7.72 нұсқасында аяқталды

Жоғарғы command row native toolbar-area ішінен жеке орталық responsive host ішіне шығарылды;
терезенің минимал өлшемі белсенді монитордың жұмыс аймағымен шектеледі. Белгі `0,01` логикалық
пиксель geometry мәнін сақтайды, кемінде бір device pixel ретінде көрсетіледі және жеке
selection/move frame қолданады. CSV/XLSX белсенді сандық DEPTH/TIME index нақты жолдарын
пайдаланады. Автоматты тексерулер аяқталды; Windows external-monitor/HiDPI/physical-print қолмен
қабылдауы ашық күйінде қалады.

Күй күні: 27 шілде 2026 жыл. Пакет нұсқасы: **0.7.72**. Project format: **v20**, form schema: **v8**, tablet layout: **v18**.

## 0.7.71 нұсқасында аяқталды

Екі жоғарғы панель терезе енімен қатаң шектеліп, F4, команда күйі, DPI және монитор өзгергеннен кейін қайта бейімделеді. Анықтамалық белгілер нақты 1×1 логикалық пиксельге дейін жіңішкереді; қалыпты аннотациялар 40×24 px минимумын сақтайды.

Кесім: 2026 жылғы 25 шілде. Пакет нұсқасы: **0.7.71**. Project format: **v20**, form schema: **v8**, tablet layout: **v18**.

## 0.7.70 нұсқасында аяқталды

- негізгі және F4 панельдері Qt жүйелік overflow қолданбайтын бір шектелген бейімделетін қатарға көшірілді;
- оң жақ өңдеу басқару элементі терезе ішінде қалады;
- анықтамалық белгілерін 2 логикалық пиксельге дейін тәуелсіз жіңішкертіп, Ctrl+S/қайта ашудан кейін өлшемін сақтауға болады.


Кесім: 2026 жылғы 25 шілде. Пакет нұсқасы: **0.7.70**. Project format: **v20**,
form schema: **v8**, tablet layout: **v18**.

## 0.7.69 нұсқасында аяқталды

- жоғарғы панель кеңейтілген, ықшам немесе аса ықшам режимді Qt логикалық пикселдеріндегі
  локализацияланған батырмалардың нақты өлшенген ені бойынша таңдайды;
- тұрақты ажыратымдылық шегі жойылды: есеп жүйелік қаріп, стиль және ағымдағы DPI-ды ескереді;
- белгіше режимі де сыймаса, басымдығы төмен командалар **«⋯»** мәзіріне өтеді;
- оң жақтағы **«Пішінді өңдеу»** ауыстырғышы жасырылатын тізімге кірмейді және панель ішінде қалады;
- қайта есептеу терезе, қаріп, стиль, DPI, экран геометриясы/жұмыс аймағы және монитор өзгергенде жүреді;
- терезені ноутбук пен сыртқы монитор арасында ауыстырғанда метрикалар бірден және кідірістен кейін тексеріледі;
- пайдаланушы құжаттамасы, release notes және регрессиялық тесттер RU/KK/EN тілдерінде синхрондалды.

## 0.7.68 нұсқасынан сақталғаны

- анықтамалық белгілері ен мен биіктік бойынша тәуелсіз созылады;
- бүйірлік маркерлер бір осьті, бұрыштық маркерлер екі осьті өзгертеді, **Shift** пропорцияны сақтайды;
- қалыпты енгізілген суреттер бұрмаланбайды;
- ен мен биіктік Undo/Redo құрамына кіреді, **Ctrl+S** арқылы сақталады, қайта ашылғанда қалпына
  келеді және экран, preview, PDF пен баспада бірдей көрсетіледі.

## Алдыңғы нұсқалардан сақталғаны

Қайталанатын **«Шкала»** жазуынсыз 44 px ықшам тақырыптар, тар геологиялық бағандар, дайын,
**18 зауыттық** және пайдаланушы пішіндерінің бірыңғай каталогы, толық пішін жасау/сақтау терезесі
және **«Диагностика деректерін тазарту…»** командасы өзгеріссіз қалады.

## Үйлесімділік

Project format, form schema және tablet layout өзгерген жоқ. Бар жобалар мен пішіндерге көшіру
қажет емес. Түбірлік `README.md` қысқа күйінде қалады және түзету тарихын қамтымайды.
