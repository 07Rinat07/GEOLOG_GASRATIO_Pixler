# Жоба жоспары

2026 жылғы 23 шілдедегі күй. Нұсқалар тарихы release notes файлдарында сақталады; мұнда
тек өзекті жұмыс бар.

## P0 — шығарылым тұрақтылығы

- [x] аннотация оқиғаларын бағыттауды және толық Qt тестінің авариялық аяқталуын түзету;
- [x] Ruff және mypy қателерін нөлге жеткізу; толық pytest нәтижесі — 1196 өтті,
  10 өткізіліп жіберілді;
- міндетті Windows, HiDPI, PDF және физикалық баспа матрицасын орындау;
- gate жасыл болғанша жинақты stable деп атамау.

## P0 — архитектура және деректер

- [x] алдымен `TabletView` ішінен annotation event router-ді мінез-құлықты өзгертпей бөліп,
  headless тесттермен қорғау;
- [x] pan/zoom/home/end/keyboard командаларын headless navigation coordinator-ға шығару;
- [x] track plan/order/reuse бөліп, Undo/Redo кезінде график даналарын сақтау;
- [x] track creation, rollback және disposal-ды байланысты registry тазалауымен шығару;
- кейін тор және өңдеу режимдерін бөлу;
- `MainWindow` класын workspace, import, print және session-binding командаларына бөлу;
- параметр түрі, quantity class, UOM, aliases, дереккөз және бастапқы мнемоникасы бар
  Semantic Channel Dictionary енгізу;
- бірыңғай Import Review және қайталанатын есеп паспортын қосу.

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
