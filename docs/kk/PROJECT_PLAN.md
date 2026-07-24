# Жоба жоспары

2026 жылғы 24 шілдедегі күй. 0.7.51 hotfix project format v20, form schema v6 және tablet
layout v16 нұсқаларын сақтайды. Windows тексеруінен кейінгі келесі пәндік кезең — read-only
offline WITSML 2.1 inventory және mapping fixtures.

## P0 — hotfix 0.7.51: диагностика және қауіпсіз қарындаш lifecycle

- [x] қолданба деректері бумасында айналмалы UTF-8 журнал жүргізу;
- [x] ұсталмаған Python/thread exceptions және толық traceback жазу;
- [x] Qt messages және Qt event handler ішінен шыққан exceptions жазу;
- [x] form apply/preview/rollback, tablet render және curve-pencil commit оқиғаларын журналдау;
- [x] журнал бумасын ашу, жолды көшіру және diagnostics ZIP құру командаларын қосу;
- [x] diagnostics ZIP ішіне LAS мәндерін, project assets және сақталған пішіндерді қоспау;
- [x] қарындаштан кейін толық rebuild орнына тек өзгерген curve tracks жаңарту;
- [x] штрихтан кейін баған ендерін, scroll position және басқа пішін виджеттерін сақтау;
- [x] толық rebuild алдында қарындашты өшіріп, stale track/curve targets тазалау;
- [x] виджеттерді ауыстырмас бұрын candidate form model тексеру;
- [x] logging, bundle privacy және lifecycle contracts headless-тесттермен бекіту;
- [ ] Windows/PySide6 smoke-test: бірнеше бағанда сурет салу, Undo/Redo және штрихтан кейін кемінде
  20 пішін ауыстыру — layout бұзылмай және Qt lifecycle қатесіз.

0.7.51 критерийі: сурет салу пішін құрылымы мен ендерін өзгертпейді; басқа пішінге өту жұмыс
істейді; кез келген қате traceback және оқиғалар реті бар бір diagnostics ZIP ретінде беріледі.

## Келесі кезеңдер

- [ ] read-only offline WITSML 2.1 inventory және mapping fixtures;
- [ ] бір пішіндегі alignment-controlled multi-dataset overlays;
- [ ] күнделікті өсімді preview арқылы растауы бар directory watcher;
- [ ] fixture replay сәтті болғаннан кейін ғана secured ETP 1.2.
