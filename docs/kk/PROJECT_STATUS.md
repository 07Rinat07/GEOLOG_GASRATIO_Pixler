# Жоба күйі

2026 жылғы 24 шілдедегі түзету тесттік жинағы: package **0.7.48**, project format **v20**,
form schema **v6**, tablet layout **v16**.

## 0.7.48 ішінде аяқталды

- кәдімгі қисық тақырыбы толық инженерлік шкалаға айналды;
- minimum/maximum шеттерде көрінеді, аралық жазулар баған торымен сәйкес келеді;
- major/minor бөліністер экран және баспа торының сақталған параметрлерін қолданады;
- linear және logarithmic жазулар бөлек интерполяцияланады;
- екі шекті дайындап, `✓` не Enter арқылы бірге қолдануға болады;
- display unit және scale type тақырыпта тікелей өңделеді;
- unit override тек көрсетуге әсер етеді, мәндерді қайта есептемейді;
- unit/range/scale/header colors tablet layout және пайдаланушы пішінінде сақталады;
- layout v15 ескі source unit мінезін өзгертпей v16-ға көшеді;
- 0.7.46–0.7.47 DB/LAS recovery және diagnostics сақталды.

Тексеру: focused suite **152 passed, 3 skipped, 3 deselected**; headless regression
**1020 passed, 4 skipped, 3 deselected**; `compileall` өтті. Windows Qt/HiDPI smoke-test міндетті.

Келесі срез: read-only offline WITSML 2.1 inventory және mapping fixtures.
