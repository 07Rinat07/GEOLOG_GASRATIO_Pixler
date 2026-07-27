# WITSML 2.x ChannelSet деректерін импорттау

## Мақсаты және шекарасы

0.7.79 нұсқасы WITSML 2.x `Log/ChannelSet` bulk-деректеріне арналған офлайн read-only parser және
атомарлық жоба импорты ағынын қосады. Parser XML, EPC/ZIP мүшесін немесе сыртқы bulk-файлды
өзгертпейді. Жоба тек Import Review дайын `Dataset`, диагностика және SHA-256 provenance бар толық
immutable `WitsmlImportCommit` жасағаннан кейін ғана өзгереді.

Ашу: **Файл → WITSML 2.x деректерін импорттау…**. Бұрынғы inventory командасы metadata-only
алдын ала тексеру болып қалады және Dataset құрмайды.

## Қолдау көрсетілетін дерек пішімі

Импортер top-level `ChannelSet` немесе WITSML `Log` ішіндегі әрбір тікелей `ChannelSet` нысанын
оқиды. ChannelSet бір немесе бірнеше `Index`, бір немесе бірнеше `Channel` және міндетті емес
`ChannelData` сипаттауы керек. Bulk-жолдар JSON-үйлесімді layout қолданады:

```text
[
  [[index-1, index-2], [channel-1, channel-2, channel-3]],
  [[index-1, index-2], [channel-1, channel-2]]
]
```

Қысқа index немесе channel массивінің соңындағы жетіспейтін мәндер `null` болып толықтырылады.
Ішкі `Data` және JSON/text файлына қауіпсіз салыстырмалы `FileUri` қолданылады. Екеуі де берілсе,
`FileUri` басым. Binary Avro деректері болжаммен талданбайды, нақты unsupported ретінде көрсетіледі.

## Қауіпсіздік шектеулері

Reader DTD/entity, бөтен namespace, қолдау көрсетілмейтін schema version, абсолютті немесе түбірден
шығатын `FileUri`, шифрланған архив мүшесі, қайталанатын жол, күмәнді compression ratio және
файл/XML element/row/cell лимиттерінің асуын қабылдамайды. ZIP/EPC мүшелері жадта оқылады және
дискідегі еркін жолға шығарылмайды.

Құрылымы дұрыс жолдың index мәні жарамсыз болса да, ол сақталады. Сондықтан Import Review оны
көрсетеді, санайды және тек оператор таңдаған саясат бойынша алып тастайды. Dataset provenance
ішінде бастапқы XML және data payload SHA-256 мәндері сақталады.

## Import Review

Диалог операторға мыналарды береді:

- Log немесе пакет ішінен ChannelSet таңдау;
- белсенді time немесе depth index таңдау;
- тек қажет scalar numeric арналарды қосу;
- source mnemonic, data type және UOM тексеру;
- canonical mnemonic, quantity class және target UOM өзгерту;
- index бойынша тұрақты сұрыптауды қосу;
- жарамсыз белсенді index бар жолдардың саясатын таңдау;
- commit алдында valid, null және invalid мәндер санын көру.

String, vector және point-metadata арналары көрінеді, бірақ әдепкіде өшірулі. Қолдау көрсетілмейтін
түрді қосу blocking diagnostic жасайды. Қайталанатын canonical mnemonic немесе semantic kind те
commit әрекетін тоқтатады.

## UOM нормализациясы

Сандық түрлендіру UOM сөздігінде нақты conversion family болғанда ғана орындалады. Мысалдар:
`ft/h → m/h`, `ft → m`, қысым, көлем, шығын, тығыздық және электр бірліктері. Жалпы quantity class
бірдей болғанымен әмбебап формуласы жоқ бірліктер үнсіз қайта таңбаланбайды. Қолдау көрсетілмейтін
немесе қайшы source/target UOM commit-ті блоктайды.

Time index timezone-aware ISO 8601 болуы керек және UTC `datetime64[ns]` форматына келтіріледі.
Сандық index арналарына қолданылатын сол қатаң UOM сервисімен түрлендіріледі.

## Dataset-ті атомарлық құру

`WitsmlImportReviewController.commit()` жоба өзгермей тұрып барлық массив, metadata, semantic
binding, index contract және provenance құрады. Содан кейін
`WitsmlProjectImportController.register()` оператор тексерген дәл сол immutable commit-ті бір
registration boundary арқылы қосады. Parsing, validation немесе registration қатесі болса,
алдыңғы current well, current Dataset және dirty state қалпына келеді.

Dataset ішінде мыналар жазылады:

- бастапқы файл/пакет мүшесі және WITSML schema version;
- ChannelSet UUID/key және таңдалған index key;
- XML және data payload SHA-256;
- source/imported/skipped row сандары;
- `[[indexes],[channels]]` layout белгісі;
- детерминирленген Dataset digest.

## Ағымдағы шектеулер

Бұл срез тек scalar numeric офлайн-деректерді импорттайды. Binary Avro, көпөлшемді channel array,
WITSML 1.4.1.1 SOAP және WITSML 2.x/ETP streaming кейінгі кезеңдерде орындалады. Бөлек Windows
WITS0 field reliability gate параллель жүреді және 0.7.79 релизімен өтті деп есептелмейді.
