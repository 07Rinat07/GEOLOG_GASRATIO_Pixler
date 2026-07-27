# WITS Level 0 қабылдау және талдау

## Мақсаты

**Файл → WITS Level 0 қабылдау...** командасы GSWITS TCP ағынын қабылдайды, кіріс байттарын
өзгеріссіз сақтайды және әр толық пакетті типтелген parser арқылы өткізеді. 0.7.76 нұсқасында
расталған Import Review-дан кейін append-only `AcquisitionSession` бастауға болады; raw шекарасы
мен parser өзгермейді, ал Dataset тек `AcquisitionController` арқылы жаңартылады.

## TCP серверін баптау

Бұл режимді GSWITS **шығыс қосылым (TCP клиенті)** ретінде бапталған кезде қолданыңыз.

1. **Кіріс қосылым — TCP сервері** режимін таңдаңыз.
2. Барлық жергілікті интерфейстер үшін `0.0.0.0`, бір интерфейс үшін оның IP мекенжайын енгізіңіз.
3. GSWITS қосылатын портты көрсетіңіз.
4. Raw каталогын таңдап, **Қабылдауды бастау** түймесін басыңыз.
5. GSWITS баптауларын сақтап, қосылым күйін тексеріңіз.

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
өрістері жазба идентификаторын, sequence number, ұңғыманы, оқпанды, күнді, уақытты және жұмыс
кодын сипаттайды. 08–99 өрістері `geoscape-gswits.json` профилімен сәйкестендіріледі.

Бұзылған жол бүкіл пакетті жоймайды. Бастапқы жол, raw мән, белгісіз `record/item` және түрлендіру
қатесі Import Review қолданатын детерминирленген discovery snapshot ішінде қалады.

## Sequence number бақылауы

Реттілік әр record нөмірі үшін бөлек бақыланады. Күйлер:

- `first` — осы record үшін бірінші sequence;
- `contiguous` — күтілген келесі мән;
- `duplicate` — соңғы мәннің қайталануы;
- `gap` — аралық мәндер жоғалған;
- `out_of_order` — ескі мән кейін келген;
- `invalid` немесе `unavailable` — 02 өрісі бұзылған не жоқ.

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
- current values және арнайы live time/depth graphs келесі кезеңде қосылады;
- reconnect әзірге жеке connection-gap records жасамайды, ал бұрын пайдаланылған ұңғыма үшін жаңа сессияға жеке саясат қажет;
- WITS0 портын интернетке тікелей ашуға болмайды;
- raw файлдар жобаны **Ctrl+S** арқылы сақтауды алмастырмайды.
