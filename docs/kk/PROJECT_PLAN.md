# Жоба жоспары

2026 жылғы 24 шілдедегі күй. 0.7.50 hotfix project format v20, form schema v6 және tablet layout
v16 нұсқаларын өзгертпейді. Windows тексеруінен кейінгі келесі өнімдік срез — read-only offline
WITSML 2.1 inventory және mapping fixtures.

## P0 — hotfix 0.7.50: пішін виджеттерінің қауіпсіз өмірлік циклі

- [x] ескі Qt ағашын жоймас бұрын header debounce таймерлерін тоқтату;
- [x] disposal кезінде minimum, maximum, unit және scale сигналдарын бұғаттау;
- [x] `deleteLater` алдында track event filter-лерін алып тастау;
- [x] layout transaction/rebuild кезінде header mutation өңдеуге тыйым салу;
- [x] snapshot ішінде widget сілтемелерін сақтамай, deep-copied `TabletLayout` арқылы қалпына келтіру;
- [x] қабылданған пішін үшін бір бастапқы rollback snapshot қолдану;
- [x] reversible apply-дан кейін Form Manager-дің екінші rollback әрекетін алып тастау;
- [x] preview Cancel кезінде бастапқы пішінге бөлек rollback сақтау;
- [x] disposal, single rollback және rebuild guard үшін headless tests қосу;
- [ ] Windows/PySide6 smoke-test: wide және narrow пішіндер арасында 20 рет ауысу, оның ішінде
  ауысар алдында minimum/maximum өзгерту.

0.7.50 критерийі: бірнеше рет ауысу `Internal C++ object already deleted` қатесін тудырмайды;
кез келген сәтсіздік жартылай планшетті емес, толық жұмыс істейтін алдыңғы пішінді қалдырады.

## Келесі кезеңдер

- [ ] read-only offline WITSML 2.1 inventory және mapping fixtures;
- [ ] бір пішіндегі alignment-controlled multi-dataset overlays;
- [ ] күнделікті өсімді preview арқылы растауға арналған directory watcher;
- [ ] сәтті fixture replay-дан кейін ғана secured ETP 1.2.
