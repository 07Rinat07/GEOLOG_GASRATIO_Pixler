# 0.7.30 шығарылымы — print jobs, session binding және workspace-командалар

## Өзгерістер

- `services/print_jobs.py` ішінде `PrintJobExecutor` жасалды: ол `QPrinter` параметрлерін
  орнатады және физикалық баспа, PDF, беттерге бөлінген растр/SVG экспортын бір renderer арқылы орындайды;
- `MainWindow` енді тек дереккөзді таңдайды, Qt диалогтарын көрсетеді, файлды ауыстыруды
  растайды және операция нәтижесін шығарады;
- жоба ашылғаннан кейін 26 session-aware controller-ді бір реестр арқылы қайта байланыстыратын
  `SessionBindingController` жасалды;
- жоба сессиясы ауысқанда Undo/Redo, уақытша таңдаулар және аяқталмаған күй тазартылады,
  сондықтан controller ескі сессиямен жұмысын жалғастырмайды;
- TIME↔DEPTH mapping/conversion және LAS range editor history қайта байланысуы түзетілді;
- жоба ағашының payload мәндерін тексеру, well/dataset контекстін таңдау және curve, track,
  lithology, stratigraphy, interpretation командаларын бағыттау үшін `WorkspaceCommandController` жасалды;
- ескірген немесе қате ағаш элементі белсенді dataset-ті жартылай өзгертпейді;
- `MainWindow` ағаш өңдегіші `current_well_id` және `current_dataset_id` мәндерін тікелей
  тағайындамайды.

## Үйлесімділік

Жоба форматы, планшет форматы, баспа параметрлері және пайдаланушы әрекеттерінің реті өзгерген
жоқ. Preview, PDF, файл экспорты және жүйелік принтер бұрынғы document model мен renderer-ді қолданады.

## Тексеру

Кеңейтілген headless/regression/source-integrity жиыны: 73 тест өтті; `compileall` және 0.7.30
wheel жинағы қатесіз аяқталды. Толық Ruff/mypy/Qt gate және физикалық принтер smoke-test барлық
тәуелділігі орнатылған Windows ортасында қайта орындалуы тиіс.
