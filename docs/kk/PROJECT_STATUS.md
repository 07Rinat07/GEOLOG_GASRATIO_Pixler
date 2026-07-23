# Жоба күйі

2026 жылғы 23 шілде: **0.7.45** тесттік жинақ, project format **v20**.

Аяқталды: осьтен тәуелсіз тор overlay; әр бағанның тор/бөлік параметрлері; қисық тақырыбындағы шкала және түстер; пішіннің revision/viewport сақталуы; 19 мөлдір тығыз қиылған белгі; тек таңдалған DEPTH/TIME dataset-ке қауіпсіз күнделікті append; SHA-256 қайталануын тану; әр dataset-тің жеке тарихы; жаңа тереңдік LAS қадамы 0,2 м.

Stable алдында Windows/HiDPI визуалды тексеруі, нақты тәуліктік LAS сынағы, толық Qt/LAS/Ruff/mypy gate және баспа тексеруі қажет. 
## Срезді тексеру

Focused forms/grid/symbols/daily-LAS/project/codec: **146 passed**. Қолжетімді headless regression: **995 passed, 4 skipped, 3 deselected**. `compileall` өтті; wheel 0.7.45 сәтті жиналды және 19 transparent-symbol asset-тің бәрін қамтиды.

Келесі срез — offline WITSML 2.1 inventory және mapping fixtures.
