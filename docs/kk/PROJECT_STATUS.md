# Жоба күйі

2026 жылғы 24 шілдедегі түзету тесттік жинағы: package **0.7.47**, project format **v20**,
form schema **v6**, tablet layout **v15**.

## 0.7.47 ішінде аяқталды

- DB тереңдік индексінің аралас реті бастапқы файлды өзгертпей қабылданған көшірмеде сұрыпталады;
- Import Review түзетілетін `D1174.db` түріндегі файлды бұғаттамайды;
- batch DB → LAS DEPT/DEPTH/MD және сақталған қолмен профильді қолданады;
- әлсіз екіұшты кандидаттар әлі де растауды қажет етеді;
- әр кәдімгі қисықтың minimum/maximum мәндері тақырыпта өңделіп, пішінде сақталады;
- auto-range, logarithmic validation, атау түсі және сызық түсі project migration-сыз сақталады;
- 0.7.46 import diagnostics орталығы сақталды.

Тексеру: focused suite **149 passed, 3 skipped, 3 deselected**; headless regression
**1012 passed, 4 skipped, 3 deselected**; `compileall` өтті, wheel 0.7.47 жиналды.
Windows DB/Qt smoke-test міндетті.

Келесі срез: read-only offline WITSML 2.1 inventory және mapping fixtures.
