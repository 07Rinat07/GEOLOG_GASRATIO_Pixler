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
