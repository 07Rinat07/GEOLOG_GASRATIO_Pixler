# WITS0 үшін Windows далалық reliability gate

## Күйі

Gate нақты GeoScape/GSWITS ағынына қосылған мақсатты Windows компьютерінде WITSML әзірлеуімен қатар
орындалады. 0.7.79 нұсқасы бағдарламалық құрал мен checklist береді, бірақ физикалық далалық gate
өтті деп жарияламайды.

## Міндетті конфигурация

Есепке компьютер, Windows build, қолданба нұсқасы және SHA-256, GSWITS connection mode, нақты
IP/port, қосылған records және intervals, raw сақтау дискі, бос орын шектері, retention policy, NTP
көзі және тест операторы жазылады. Vendor screenshot ішіндегі порттар тек мысал және әдепкі мән
ретінде қолданылмайды.

## Минималды іске қосу

Кемінде 8 сағат, мүмкін болса 24 сағат. Қалыпты ағын, басқарылатын GSWITS restart, ашық acquisition
session кезінде қолданба restart, желі үзілуі және қалпына келуі, raw rotation, project save/reopen,
live-monitor pause/resume және history қарау тексеріледі.

## Қабылдау дәлелдері

`.wits` raw segment, chunk index, connection journal, recovery manifest, project файлы, application
log, JSON soak report және connection/live-monitor screenshot сақталады. Мыналар тексеріледі:

- қабылданған әр TCP байтының raw reference бар;
- connection ID және disconnect reason толық;
- replay және live capture parser/discovery нәтижелері бірдей;
- restart кейін acquisition sequence және checkpoints жалғасады;
- disk warning/critical шектері конфигурацияға сәйкес;
- retention белсенді raw файлды өшірмейді;
- unhandled exception, UI freeze немесе тұрақты memory growth жоқ;
- соңғы recovery manifest clean shutdown көрсетеді.

Кез келген орындалмаған критерий gate-ті ашық қалдырады. Есепте қате timestamp, connection ID, raw
segment және түзетуші build көрсетіледі.
