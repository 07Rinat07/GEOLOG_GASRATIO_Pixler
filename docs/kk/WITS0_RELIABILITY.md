# WITS0 сенімділігі, қалпына келтіру және soak-тестілеу

## Қамту аймағы

0.7.78 қабаты WITS0 бастапқы ағынын және ашық append-only `AcquisitionSession` нысанын желі
үзілуінен, диск орнының азаюынан, процестің апаттық тоқтауынан және live-view баптауларының
жоғалуынан қорғайды. Қалпына келтірудің негізгі көзі — raw байттар; parser, mapping немесе Dataset
қатесі қабылданған деректі жоймауы тиіс.

## Қосылу жазбалары

Әр TCP қосылымына тұрақты `connection_id` беріледі. Worker іске қосылу, тоқтау, қосылу және ажырау
оқиғаларын append-only JSONL журналына жазады. Ашық `AcquisitionSession` кезінде бұл шекаралар
`AcquisitionController` арқылы `OperationalEventKind.CONNECTION` түріндегі типтелген оқиғаларға да
қосылады. Peer, себеп, raw сегмент, байттар және frame саны сақталады, бірақ жалған Dataset жолдары
жасалмайды.

## Диск бақылауы және retention

`Wits0DiskSpaceGuard` raw жазу алдында және socket күту кезінде бос орынды тексереді. Warning күйінде
жұмыс жалғасады; critical күйінде келесі raw жазу тоқтатылып, қосылым `critical_free_space`
себебімен жабылады. `Wits0RawRetentionManager` тек белсенді емес `.wits` сегменттері мен белгілі
sidecar файлдарын өшіреді, ағымдағы сегментті қорғайды және жас/көлем/минимум лимиттерін қолданады.
Журналдар, manifest және жобалар өшірілмейді.

## Қайта іске қосқаннан кейін қалпына келтіру

Атомарлық `.wits0-recovery.json` run, қосылым, ағымдағы сегмент, соңғы қабылдау уақыты, acquisition
session және custom profile контекстін сақтайды. Келесі іске қосу таза емес тоқтауды анықтайды.
Қиылған chunk-index JSONL соңы атомарлы түзетіледі, индекстелмеген raw бөлігі есепке жазылады;
`.wits` байттары өзгертілмейді.

Жобадағы ашық WITS0 сессиясы immutable schema және нұсқаланған custom profile арқылы жалғасады;
реттілік пен checkpoints сақталады. Жабық сессия автоматты ашылмайды.

## Workspace сақтау

Per-well `QSettings` ішінде axis mode, auto-follow, pause-view, follow span, rendering budget,
таңдалған қисықтар, history range және белсенді session ID сақталады. Бұл тек көрсету күйі.

## Windows soak-тесті

```powershell
.\scripts\run_wits0_soak_test.ps1 -DurationHours 8 -RateHz 20
```

Headless құрал TCP chunks шекараларын кездейсоқ бөледі, reconnect, sequence gaps, duplicates және
malformed values жасайды және JSON есеп береді. Синтетикалық loopback нақты GeoScape GSWITS далалық
soak-тестін алмастырмайды.

## Шекаралар

Windows Service орнатылмайды, белсенді raw өшірілмейді, жабық сессия қайта ашылмайды және нақты
далалық soak өтті деп жарияланбайды. Service/startup бағалауы, signed checklist, физикалық disk-full
және ұзақ GSWITS тексеруі қабылдау жұмысы болып қалады.
