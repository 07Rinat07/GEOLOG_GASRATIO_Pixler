# GEOLOG GASRATIO@Pixler 0.7.76 — WITS0 normalized batches және append-only AcquisitionSession

## Кезеңнің мақсаты

0.7.76 нұсқасы WITS0 интеграциясының D кезеңін аяқтайды. Расталған Import Review енді типтелген WITS0 frames деректерін immutable normalized measurement batches түріне айналдырады және growing Dataset жазбасын тек `AcquisitionController` арқылы орындайды.

## WITS0 қалыпқа келтіру

- `Wits0FrameNormalizer` immutable `Wits0ImportReviewCommit` және schema digest қолданады;
- WITS header күні/уақыты `DATETIME` index үшін UTC Unix nanoseconds мәніне айналады;
- depth/time field index тек таңдалған `record/item` көзінен алынады;
- жоқ curve мәндері `None`, кейін Dataset ішінде `NaN` ретінде жазылады;
- белгісіз сандық vendor field расталған numeric mapping арқылы қолданыла алады;
- duplicate, invalid және out-of-order source sequence әдепкіде жол құрмайды;
- raw SHA-256, source record, source sequence, reception timestamp және raw reference batch/record provenance құрамына кіреді;
- бірдей timestamps/source references кезінде live және replay бірдей normalized batches береді.

## Bounded queue және backpressure

`AcquisitionController` атомдық `enqueue_many()` және `remaining_capacity` алды. Кіріс batch bounded queue ішіне толық орналасады немесе queue өзгермейді. `Wits0AcquisitionRuntime` `RAISE` және `DRAIN_THEN_RETRY` саясаттарын қолдайды, backpressure events санайды және acquisition sequence ретін бұзбайды.

## Checkpoints және controlled close

Runtime checkpoints жазылған records саны немесе уақыт бойынша жасайды, бірақ pending queue бос болғанда ғана. Controlled close қабылдауды тоқтатады, queue толық босатады, final checkpoint жасайды және `AcquisitionSession` күйін сәйкес final audit digest арқылы `closed` етеді. Жабық сессия project format v20 миграциясынсыз сақталып, қайта ашылады.

## Интерфейс

**Файл → WITS Level 0 түсіру...** терезесі өзекті Import Review кейін:

1. ағымдағы ұңғыма үшін acquisition-сессияны бастайды;
2. pending/applied/skipped/backpressure/checkpoint counters көрсетеді;
3. bounded queue қолмен жазады;
4. controlled close орындайды;
5. project tree ішінде growing WITS0 Dataset автоматты түрде таңдайды.

Network socket worker thread ішінде қалады, ал project mutation immutable events polling кезінде GUI thread ішінде орындалады.

## Тексеру

Автоматты тесттер time/depth index, sparse rows, unknown numeric fields, duplicate/out-of-order policy, live/replay equivalence, atomic batch enqueue, backpressure, checkpoint policy, controlled close және project round-trip жағдайларын қамтиды. Толық GUI runtime үшін PySide6/pyqtgraph бар Windows ортасы және нақты anonymized GSWITS raw stream қажет.

## Үйлесімділік

Project format — **v20**, form schema — **v8**, tablet layout — **v18**. Қолданыстағы жобаларға migration қажет емес. 50% ықшам бағандар, дайын 48/80 ендері, барлық дайын және пайдаланушы пішіндері, Ctrl+S арқылы сақтау және қайта ашу өзгеріссіз қалады.
