# Жоба жоспары

0.7.77 кезеңінен кейін 2026 жылғы 27 шілдеге өзекті. Бұл файлда тек аяқталмаған жұмыс берілген; орындалған кезеңдер
[жоба күйінде](PROJECT_STATUS.md), түбірлік [өзгерістер тарихында](../CHANGELOG.md) және release
notes ішінде сақталады.


## Басымдық: WITS0 live monitor және далалық сенімділік

Raw capture, типтелген parser, Import Review, normalized batches, append-only
`AcquisitionSession` және негізгі `AcquisitionLiveView` monitor дайын. Аяқталмаған жұмыс:

- [ ] 5–10 минут нақты GSWITS raw деректерін алу;
- [ ] TCP mode, IP, порт, encoding, header fields және record интервалдарын растау;
- [ ] кірістірілген GeoScape profile және custom profile-ды нақты record/item мәндерімен салыстыру;
- [ ] таңдалған арналар, axis mode, диапазондар және follow mode-ты workspace settings ішінде сақтау;
- [ ] connection events және connection-gap markers-ті acquisition records ретінде қосу;
- [ ] бірліктері үйлеспейтін арналар үшін тәуелсіз tracks/scales қосу;
- [ ] алдыңғы сессия жабылғаннан кейін жаңа сессия саясатын анықтау;
- [ ] Windows reconnect/soak/restart/disk-full тексеруін орындау.

## GeoScape II GS2 қабылдауы

- [ ] басқа GeoScape нұсқалары үшін versioned projection және жасырын Access/Paradox fixtures қосу;
- [ ] бүлінген, кесілген және multipart кестелерді reproducible golden fixtures арқылы тексеру;
- [ ] СГ-8 және кемінде екі басқа GS2 файлын GeoScape эталондық LAS/Excel export-пен салыстыру;
- [ ] C1–C5, total gas, TIME/DEPTH, бірліктер, диапазондар және файл бөлінуін растау;
- [ ] `GS2.mdb` арқылы дәлелденген арналарда Gas Ratio/Pixler жұмысын тексеру.

Сандық TIME CSV/XLSX автоматты тесті ортақ resolved-export жолын растайды, бірақ нақты эталондық
LAS/Excel салыстыруын алмастырмайды.

## 0.7.72 қолмен қабылдау

- [ ] Windows жүйесінде екі command row-ды 100%, 125% және 150% DPI кезінде тексеру;
- [ ] F4 және қайталанатын әрекеттермен терезені ноутбук пен сыртқы монитор арасында ауыстыру;
- [ ] transparent және original белгілерді сегіз marker, **Shift** және rotation арқылы тексеру;
- [ ] аса жіңішке белгіні **Ctrl+S** және reopen кейін қайта таңдау, жылжыту және resize жасау;
- [ ] `0,01` логикалық пиксель geometry үшін screen, preview, PDF және physical print салыстыру.

## Release recovery

- [ ] ағымдағы mypy findings және internal error мәселесін жою;
- [ ] tablet/annotation/PDF/HiDPI/physical-printer signed smoke checklist орындау;
- [ ] міндетті gate толық жасыл болғаннан кейін ғана stable build жариялау.

## Қабылдау шарты

Терезе белсенді монитордың жұмыс аймағынан шықпайды, оң жақ edit командасы қолжетімді қалады,
ал аса жіңішке белгі сақталған geometry өзгермей көрінеді, таңдалады және өңделеді. CSV/XLSX
белсенді сандық DEPTH/TIME осінің нақты жолдарын пайдаланады.
