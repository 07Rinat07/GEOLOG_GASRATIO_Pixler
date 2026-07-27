# WITS0 AcquisitionSession

## Мақсаты

Бұл құжат **Import Review** расталғаннан кейінгі кезеңді сипаттайды. Сессия басталғанға дейін қолданбада тексерілген `AcquisitionDatasetSchema`, таңдалған index және versioned custom profile бар immutable `Wits0ImportReviewCommit` болуы керек.

## Конвейер

```text
Wits0ParsedFrame
    ↓ Wits0FrameNormalizer
Wits0MeasurementBatch
    ↓ bounded queue
AcquisitionRecord(DATA_ROW)
    ↓ AcquisitionController
append-only Dataset + AcquisitionSession
```

Raw `*.wits` өзгермейді. Normalizer бастапқы frame SHA-256, `record/item`, source sequence, reception timestamp және raw reference сақтайды.

## Index

`header:datetime` үшін 05 және 06 items расталған timezone арқылы біріктіріліп, UTC форматына ауысады және Unix nanoseconds ретінде сақталады. Depth/time field index үшін тек таңдалған field қолданылады. Дұрыс index жоқ frame жол құрмайды.

## Channel мәндері

Әр жол immutable schema ішіндегі curve IDs толық жиынын қамтиды. Дұрыс сан `float` ретінде жазылады; жоқ немесе бүлінген мән `None`, Dataset ішінде `NaN` болады. Таңдалған index field curve ретінде қайталанбайды.

## Sequence policy

Parser source sequence мәнін әр WITS record үшін бөлек бақылайды. Әдепкіде duplicate, invalid және out-of-order frames өткізіледі; gap рұқсат етіледі және diagnostics ішінде қалады. Acquisition sequence source sequence емес: ол `AcquisitionSession` ішінде 1-ден басталып, үздіксіз болады.

## Bounded queue және backpressure

`AcquisitionController.enqueue_many()` бүкіл batch үшін capacity, sequence, record IDs және schema алдын ала тексереді. Кез келген қате кезінде pending queue өзгермейді. `RAISE` саясаты backpressure қайтарады; `DRAIN_THEN_RETRY` pending records бөлігін қолданады және enqueue әрекетін бір рет қайталайды.

## Checkpoints

Checkpoint pending queue бос болғанда ғана жасалады. Runtime applied records саны және уақыт интервалы бойынша threshold қолдайды. Checkpoint sequence, row count, Dataset digest, events digest және audit digest бекітеді.

## Controlled close

Controlled close:

1. жаңа frames қабылдауын тоқтатады;
2. pending queue толық босатады;
3. final checkpoint жасайды;
4. `closed_at` орнатады;
5. final audit digest жазады;
6. session күйін `closed` етеді.

Close кейін жаңа records қабылданбайды. Сақталған project қайта ашылып, append-only projection тексеріледі.

## Оператор интерфейсі

WITS0 терезесінде **Сессияны бастау**, **Кезекті жазу** және **Сессияны жабу** командалары бар. Status pending records, applied rows, skipped frames, checkpoints және backpressure көрсетеді. Белсенді сессия кезінде терезені жабу TCP worker тоқтағаннан және қалған immutable events өңделгеннен кейін controlled close орындайды.

## Ашық далалық қабылдау

Кірістірілген GeoScape mapping нақты anonymized GSWITS raw stream арқылы расталуы керек. Windows жүйесінде reconnect, ұзақ жазу, disk full, авариялық аяқталу, project қайта ашу және live/replay Dataset digests сәйкестігі тексеріледі.
