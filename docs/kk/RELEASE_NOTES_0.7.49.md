# GEOLOG GASRATIO@Pixler 0.7.49 — бейімделетін шкала және пішінді транзакциялық ауыстыру

## Түзетулер

- жаңа және автоматты materialize жасалған қисықтар әдепкіде linear scale қолданады;
- тақырыптағы minimum/maximum render key құрамына кіреді және қисықтың normalized X-геометриясын бірден қайта салады;
- manual range қысқа кідірістен кейін автоматты немесе Enter арқылы бірден қолданылады;
- тар бағанда minimum және maximum қолжетімді енді бөліседі және жоғалмайды;
- unit және linear/logarithmic таңдау бөлек бейімделетін қатарда орналасады;
- инженерлік ruler нақты бағанның major/minor divisions параметрлерін сақтайды;
- пішін алдымен толық render жасалып, содан кейін ғана session ішінде commit болады;
- render не commit қатесі соңғы жұмыс істеген пішінді, dirty-state және таңдалған track-ті қайтарады;
- preview-дан кейін manager-ді Cancel ету бастапқы жұмыс конфигурациясын қалпына келтіреді;
- таңдалған пішінді қауіпсіз қолдану мүмкін болмаса, manager-ден print басталмайды.

## Үйлесімділік

- package: **0.7.49**;
- project format: **v20**;
- form schema: **v6**;
- tablet layout: **v16**;
- project migration қажет емес;
- әдейі сақталған logarithmic қисықтар өзгермейді, linear default тек жаңа және автоматты bindings үшін қолданылады.

## Тексеру

Тексеру: **150 focused passed**; қолжетімді headless regression — **1037 passed, 4 skipped, 3 deselected**; `compileall` және wheel build орындалды. Build ортасында PySide6 және pyqtgraph жоқ, сондықтан тар баған, HiDPI және form rollback Windows жинағында қосымша тексеріледі.
