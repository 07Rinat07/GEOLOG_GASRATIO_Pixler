# Жоба жоспары

2026 жылғы 23 шілдедегі күй. Нұсқалар тарихы release notes файлдарында сақталады; мұнда
тек өзекті жұмыс бар.

## P0 — шығарылым тұрақтылығы

- [x] аннотация оқиғаларын бағыттауды және толық Qt тестінің авариялық аяқталуын түзету;
- [x] Ruff және mypy қателерін нөлге жеткізу; 0.7.28 baseline нәтижесі — 1217 өтті,
  10 өткізіліп жіберілді;
- міндетті Windows, HiDPI, PDF және физикалық баспа матрицасын орындау;
- ағымдағы нұсқа үшін толық Ruff/mypy/pytest gate-ті қайталау;
- gate жасыл болғанша жинақты stable деп атамау.

## P0 — архитектура және деректер

- [x] `TabletView` ішінен annotation event router-ді мінез-құлықты өзгертпей шығару;
- [x] pan/zoom/home/end/keyboard командаларын headless coordinator-ға шығару;
- [x] track plan/order/reuse, creation, rollback және disposal бөліктерін шығару;
- [x] экран/баспаға ортақ grid renderer-ді шығару;
- [x] өңдеу режимі контроллерін F4 және аннотация құралы күйінің жалғыз иесі ету;
- [x] басты бет/workspace/мақсатты қойынды навигациясын `MainWindow` ішінен шығару;
- [x] әмбебап import маршрутизациясын және CSV/Excel/LAS/Paradox jobs-ты шығару;
- [x] print jobs, session binding және жоба ағашының workspace командаларын шығару;
- [x] UI кластарының сериализацияланатын жоба моделін тікелей өзгертуіне тыйым салу;
- [x] параметр түрі, quantity class, UOM, aliases, дереккөз және бастапқы мнемоникасы бар
  Semantic Channel Dictionary енгізу және binding-ті project format v16 ішінде сақтау;
- [x] manual overrides, QC preview және атомарлық commit бар интерактивті Import Review қосу;
- [x] fingerprints, bindings/UOM, formula versions, form revision, language және render settings бар қайталанатын есеп паспортын енгізу;
- келесі қадамда экран және баспа геометриясына golden fixtures қосу.

## P1 — операциялар және нақты уақыт

- типтелген drilling/gas/show/sample/casing/top оқиғалары;
- gap, duplicate, out-of-order, stale және calibration QC;
- acquisition source-ты өзгертпейтін нұсқаланған lag/depth correction;
- WITSML 2.1 inventory, кейін recorded replay, соңында қорғалған ETP 1.2 client.

## P1 — есептер

- preview, PDF және кестелік экспортқа ортақ аралық моделі;
- ортақ bindings, UOM, coverage және нөл/бос мәнді анық ажырату;
- A4/A3/custom/roll, 100%/fit және бет жалғасын тексеру.

## P2 — дамыту

- tops, ties және PDF бар multiwell correlation;
- crossplot және статистикалық графиктер;
- шектеулі нұсқаланған API және журналы мен рұқсаты бар Python console.

Толық критерийлер: [инженерлік жоспар](../PROJECT_PLAN.md). Негіздеме:
[аудит](PRODUCT_AUDIT_2026.md).
