# Append-only acquisition және deterministic replay

Күйі: 0.7.42 нұсқасында іске асырылды. Acquisition schema: v1. Ағымдағы project format: v20 (acquisition v18-де енгізілген).

Жазылған `AcquisitionSession` — бастапқы дереккөз. Growing `Dataset` және
`operational_events` — сол жолдар, оқиғалар, QC flags және есеп деректерін дәл қайталауға тиіс
тексерілетін проекциялар.

## Contract

- бір session immutable index және curve schema-ны бекітеді;
- records үздіксіз sequence және `DATA_ROW`, `EVENT_UPSERT` немесе `EVENT_DELETE` түрін қолданады;
- жолдар тек қосылады, missing curve sample `NaN` болады;
- bounded buffer нақты backpressure қайтарады және record жоғалтпайды;
- apply қатесі dataset, events және source journal күйін атомарлы қайтарады;
- checkpoint row count, dataset/events fingerprints және ортақ audit digest-ті бекітеді;
- replay жұмыс көшірмесінде нөлден басталады немесе тек сәйкес checkpoint-тен кейін жалғасады, metadata/fingerprints тексеріп, тек толық күйде commit жасайды;
- жабық session final checkpoint және сәйкес final audit digest талап етеді.

Project format v18 session-дарды енгізді; ағымдағы v20 оларды `well.acquisition_sessions` ішінде сақтайды. `v17 → v18`
migration бос collection қосып, бар деректерді өзгертпейді. Нұсқаланатын lag/depth correction
0.7.44 ішінде бөлек derived projection ретінде іске асырылды және append-only source-ты өзгертпейді.

## Пакеттік materialization

Live mutation 64 record-тан тұратын атомарлық batch арқылы орындалады. Index және curve массивтері
геометриялық capacity арқылы өсіп, тек logical slice жариялайды; failed mixed data/event batch толық
проекцияны көшірмей logical row count, curve versions, events және incremental
record/dataset/events hash chains күйін қайтарады. Streaming кезінде `AcquisitionApplyResult`
`digest_mode=incremental_chain` қолданады. Үйлесімді толық dataset/events fingerprints тек checkpoint
және `current_result()` шекараларында есептеледі. Replay сол batch boundary-ді қолданып, әр persisted
checkpoint алдында batch-ті аяқтайды.
