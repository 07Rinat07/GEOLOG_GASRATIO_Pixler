# GEOLOG GASRATIO@Pixler 0.7.75 — WITS0 Import Review және immutable AcquisitionDatasetSchema

## WITS0 Import Review

- Барлық data `record/item`, type, UOM, дұрыс/NULL/error саны, сандық диапазон және шектелген samples жинайтын Qt-тәуелсіз `Wits0DiscoveryAccumulator` қосылды.
- Discovery snapshot immutable және live/replay үшін детерминирленген. Fingerprint mapping surface-ті сипаттайды, сондықтан бар өрістердің қосымша мәндері расталған схеманы ескіртпейді.
- Жаңа немесе өзгерген `record/item`, inferred value kind/UOM не алғаш қолжетімді header datetime fingerprint-ті өзгертіп, schema күйін stale етеді.
- `Wits0ImportReviewController` draft, preview және atomic commit шекараларын бөледі; тексеру кезінде raw bytes, parser output және жоба өзгермейді.
- Жаңа диалог барлық анықталған өрістерді және бұғаттайтын/ескертетін QC findings көрсетеді.

## Semantic mapping, UOM және index

- Автоматты mapping ұсыныстары қолданыстағы Semantic Channel Dictionary арқылы жасалады.
- Әр арнада canonical mnemonic, semantic kind, quantity class, source UOM және canonical UOM растауға немесе өзгертуге, не арнаны алып тастауға болады.
- Active index үміткерлері WITS header date+time және жарамды numeric time/depth fields арқылы жасалады.
- Таңдалған index field Dataset curve ретінде қайталанбайды.
- Non-numeric channels, үйлеспейтін quantity classes және қажетті сандық UOM conversion commit-ті бұғаттайды.
- Белгісіз record/item үнсіз жойылмай, manual mapping үшін сақталады.

## Immutable schema және versioned custom profile

- Сәтті растау `AcquisitionIndexSchema`, `AcquisitionCurveSchema`, `CurveMetadata` және semantic provenance бар immutable `AcquisitionDatasetSchema` атомарлық жасайды.
- Schema аудит және кейінгі `AcquisitionSession` үшін тұрақты SHA-256 digest алады.
- Пайдаланушы mapping-і exclusive-create арқылы бөлек `<profile-id>.vN.json` файлына сақталады; кірістірілген `geoscape-gswits.json` өзгермейді.
- Алдыңғы profile келесі revision негізі бола алады; profile ID/version base profile-мен тексеріледі.
- Қабылдау терезесіне **Импортты тексеру…**, **Анықтауды тазарту**, анықталған арна саны, schema күйі, digest және versioned profile жолы қосылды.

## Шектеулер және келесі кезең

- C кезеңі үйлесімді бірліктер арасында сандық conversion жасамайды; source және canonical UOM бір канондық бірлікке шешілуі тиіс.
- Растау `AcquisitionSession` әлі бастамайды және Dataset жолдарын қоспайды.
- Кірістірілген GeoScape mapping нақты жасырын GSWITS raw ағынымен салыстырылуы тиіс.
- Келесі D кезеңі: WITS frame → normalized measurement batch → `AcquisitionController` арқылы append-only `AcquisitionSession`, checkpoints, bounded queue және backpressure.

## Үйлесімділік

Project format `v20`, form schema `v8`, tablet layout `v18` болып қалады; migration қажет емес. Барлық дайын және пайдаланушы пішіндері, **Пішін жасау**, **Пайдаланушы пішінін сақтау**, қайталанатын атау мен бос орыннан қорғау, `50%`, `48`, `80` ықшам бағандары, **Ctrl+S** және қайта ашу өзгеріссіз сақталды.
