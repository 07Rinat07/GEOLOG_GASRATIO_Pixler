# Жоба күйі

2026 жылғы 24 шілдедегі түзету тесттік жинағы: package **0.7.49**, project format **v20**,
form schema **v6**, tablet layout **v16**.

## 0.7.49 ішінде аяқталды

- жаңа және автоматты жасалған қисықтар әдепкіде linear scale қолданады;
- manual minimum/maximum render key құрамына кіріп, қисық геометриясын қайта салады;
- range қысқа кідірістен кейін немесе Enter арқылы бірден қолданылады;
- responsive header тар бағанда minimum, maximum, unit және scale type сақтайды;
- engineering ruler нақты баған grid major/minor divisions параметрлерін қолданады;
- жаңа пішін session commit алдында render жасалады;
- render/commit қатесі соңғы жұмыс пішінін, dirty-state және selected track-ті қалпына келтіреді;
- Form Manager Cancel preview алдында болған конфигурацияны қайтарады;
- бұрын анық сақталған logarithmic bindings өзгермейді;
- project/form/layout schema өзгермеді, migration қажет емес.

Тексеру: focused **150 passed**; headless regression **1037 passed, 4 skipped, 3 deselected**; `compileall` және wheel build
орындалды. PySide6/pyqtgraph жоқ болғандықтан Windows Qt/HiDPI, тар баған және rollback smoke-test
міндетті.

Келесі срез: read-only offline WITSML 2.1 inventory және mapping fixtures.
