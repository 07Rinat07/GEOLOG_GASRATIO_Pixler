# Жоба күйі

2026 жылғы 24 шілдедегі жедел тесттік жинақ: package **0.7.46**, project format **v20**.

Hotfix аяқталды: PySide6 grid-overlay mouse-button типі түзетілді; presentation қатесі импортталған LAS-ты жасырмайды; қауіпсіз кестелік recovery бар; Import Review warning-тері бұғаттамайды; кезеңдік әрекетке жарамды diagnostic report көшіруге, сақтауға және blocking қате кезінде автоматты жазуға болады; қайталанатын mnemonic физикалық баған бойынша оқылады, бір зақымдалған арна бүкіл файлды тоқтатпайды.

Project format v20, form schema v6, tablet layout v15, бірнеше DEPTH/TIME datasets, сақталған пішіндер, белгілер, annotation, қисық параметрлері және күнделікті LAS append өзгермеді.

Тексеру: **76 focused passed**; қолжетімді headless regression **1011 passed, 4 skipped, 3 deselected**; `compileall` өтті және wheel 0.7.46 жиналды. Контейнерде PySide6, pyqtgraph, lasio, Ruff және mypy жоқ, сондықтан нақты LAS-пен Windows/HiDPI first-frame smoke-test және толық gate міндетті.

Windows растауынан кейінгі келесі срез: read-only offline WITSML 2.1 inventory және mapping fixtures.
