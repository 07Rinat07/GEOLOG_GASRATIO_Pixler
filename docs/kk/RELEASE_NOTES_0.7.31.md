# 0.7.31 шығарылым ескертпелері — жоба моделін өзгерту шекарасы

## Өзгерістер

- планшеттің сериализацияланатын layout өзгерістері Qt view ішіндегі тікелей меншіктеудің орнына
  `TabletLayoutMutationController` және `TabletController` арқылы орындалады;
- track resize/reorder, тік индекс және көрінетін аралық қимылдары бұрынғы әрекет пен Undo/Redo-ны
  сақтайды, ал commit controller шекарасының артында орындалады;
- `MainWindow` енді `session.dirty`, project collections және ағымдағы layout мәндерін тікелей
  өзгертпейді;
- `DerivedDatasetController` merge/external-LAS copy алдында checkpoint жасап, тоқтатылған немесе
  қате export кезінде rollback орындайды;
- rollback уақытша dataset пен layout/source/import-report sidecar деректерін жойып, бастапқы
  well/dataset таңдауы мен `dirty` күйін қалпына келтіреді;
- merge нәтижесінің атауы dataset тіркелмей тұрып тексеріледі;
- Masterlog тақырыбының image assets жиыны бір атомарлық controller шақыруымен тексеріліп орнатылады;
- session registry енді 27 контроллерді қайта байланыстырады;
- шекараны қорғайтын headless, regression және source-integrity тесттері қосылды.

## Үйлесімділік

Жоба форматы 15, layout форматы 14 және пайдаланушы сценарийлері өзгерген жоқ. Бастапқы LAS
файлдары өзгертілмейді; тек commit/rollback иесі ауысты.

## Тексеру

714 қолжетімді тест өтті, 4 платформалық сценарий өткізіліп жіберілді; `compileall` және 0.7.31
wheel жинағы сәтті аяқталды. Толық Qt/LAS pytest, Ruff, mypy және
Windows/HiDPI/PDF/физикалық баспа gate-і орнатылған ортада қайта орындалуы тиіс.
