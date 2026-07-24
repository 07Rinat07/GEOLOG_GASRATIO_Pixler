# Жоба күйі

2026 жылғы 24 шілдедегі түзету жинағы: package **0.7.50**, пішін виджеттерінің өмірлік цикліне
арналған маңызды түзету. Project format: **v20**, form schema: **v6**, tablet layout: **v16**.

## 0.7.50 ішінде аяқталды

- `CurveHeaderEditor` үшін айқын idempotent disposal келісімі қосылды;
- range debounce таймері `deleteLater` алдында тоқтайды, өріс сигналдары бұғатталады;
- әр трек Qt ағашын жоймас бұрын header callback-тарын тоқтатып, event filter-лерді алып тастайды;
- планшет қайта құрылып жатқанда ескі шапкадан келген range/unit/scale өзгерістері еленбейді;
- rollback жойылған виджеттерді қайта қолданбай, `TabletLayout` моделінен жаңа Qt ағашын құрады;
- Form Manager бастапқы snapshot-ты бір reversible transaction-ға береді және сәтсіз apply-дан
  кейін екінші бәсекелес rollback орындамайды;
- preview-ды болдырмау бастапқы пішінді, dirty-state пен таңдалған тректі қалпына келтіреді;
- project/form/layout schema өзгермеді, migration қажет емес.

## Тексеру

- focused form/layout/lifecycle: **171 passed**;
- қолжетімді headless regression: **1044 passed, 4 skipped, 4 deselected**;
- `compileall` сәтті орындалды;
- PySide6 бар Windows smoke-test жылдам бірнеше рет пішін ауыстыруды және
  `Internal C++ object already deleted` қатесінің жойылғанын тексеруі тиіс.

## Келесі вертикалдық срез

Read-only offline WITSML 2.1 inventory және mapping fixtures. Fixture replay аяқталғанша ETP 1.2
бұғатталған күйде қалады.
