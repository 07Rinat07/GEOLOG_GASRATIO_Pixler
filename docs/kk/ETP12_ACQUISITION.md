# ETP 1.2 ChannelData жазу

0.7.82 нұсқасы расталған ETP ChannelData деректерін өзгермейтін normalized measurement batch және append-only AcquisitionSession жазбаларына түрлендіреді.

## Тұрақты сәйкестік

ETP арнасының сандық ID мәндері тек бір келісілген сессия ішінде жарамды және reconnect кейін өзгеруі мүмкін. Сондықтан mapping, семантикалық сәйкестік және дедупликация Channel URI арқылы орындалады. Әр batch ағымдағы `channel_id -> URI` картасын және subscription generation мәнін алып жүреді. Fingerprint уақытша ID, generation және sample статистикасына тәуелді емес.

## Import Review

`Etp12DiscoveryAccumulator` ChannelMetadata және қабылданған мәндердің статистикасын біріктіреді. Import Review scalar numeric арналарды, canonical mnemonic, semantic kind, quantity class, бастапқы және мақсатты UOM, сондай-ақ уақыт немесе тереңдік индексін растайды. Commit immutable `AcquisitionDatasetSchema` жасайды; metadata surface өзгерсе, бұрынғы review ескі деп белгіленеді.

## Нормализация

`Etp12ChannelNormalizer` нүктелерді canonical index бойынша топтайды, ETP микросекунд уақытын Unix наносекундтарына түрлендіреді және тек анық көрсетілген UOM conversion орындайды. Әр жол schema жариялаған curve жиынын дәл қамтиды; жоқ мәндер null болып, growing Dataset ішінде NaN түрінде сақталады. Қате index және numeric емес мәндер structured diagnostic ретінде қалады.

## Reconnect overlap

Әр қабылданған нүктеге schema digest, Channel URI, normalized index және normalized value негізінде тұрақты SHA-256 есептеледі. Bounded deduplication window subscription қалпына келгеннен кейінгі дәл overlap-ты, numeric channel ID өзгерсе де, жояды. Сол index-тегі өзгерген value жаңа append-only дерек болып қалады. Point hash AcquisitionRecord provenance ішінде жазылады.

## Runtime және қалпына келтіру

`Etp12AcquisitionRuntime` bounded enqueue, atomic multi-row insertion, backpressure, periodic checkpoint және controlled close ұсынады. Жоба қайта ашылғаннан кейін ағымдағы ChannelMetadata алынғанда open session қалпына келеді. Соңғы deduplication window persisted provenance арқылы қайта құрылады. Project format v20 болып қалады.
