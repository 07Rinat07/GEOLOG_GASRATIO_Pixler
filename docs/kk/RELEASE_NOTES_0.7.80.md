# GEOLOG GASRATIO@Pixler 0.7.80 — WITSML 1.4.1.1 SOAP тек оқу

## Тек оқуға арналған Store API клиенті

`WMLS_GetVersion`, `WMLS_GetCap` және `WMLS_GetFromStore` операциялары үшін қатаң SOAP 1.1 клиенті
қосылды. Store өзгерту операцияларына тыйым салынған. Well → Wellbore → Log → LogCurveInfo →
LogData иерархиясы қолдау табады.

## Желі сенімділігі және аудит

Әр сұрауда тайм-аут, шектелген қайталау, жауап өлшемінің лимиті және DTD/entity тыйымы бар.
Аудит SHA-256 тізбегімен append-only JSONL түрінде жазылады. XML сұрауы, құпиясөз және
Authorization тақырыбы аудитке түспейді.

## Credentials жоба файлынан тыс

Профильде URL, пайдаланушы аты, credential идентификаторы және ашық параметрлер ғана сақталады.
Windows жүйесінде құпиясөз Windows Credential Manager ішінде сақталады. Linux әзірлеу ортасында
тұрақты емес memory store қолданылады. Credentials Dataset немесе жоба файлына жазылмайды.

## Import Review қайта пайдаланылады

Алынған WITSML 1.4.1.1 LogData қолданыстағы immutable ChannelSet моделіне түрленеді. Одан кейін
WITSML 2.x офлайн импортымен бірдей Semantic Channel Dictionary, UOM conversion, Import Review,
Dataset digest және атомарлық тіркеу қолданылады.

Нақты GSWITS-пен параллель Windows field reliability gate әлі ашық. Project format — v20, form
schema — v8, tablet layout — v18.
