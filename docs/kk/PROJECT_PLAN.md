# Жоба жоспары

2026 жылғы 24 шілдеге өзекті. **0.7.60** нұсқасы project format v20, form schema v6 және tablet layout v16 сақтайды.

## P0 — 0.7.60: экран шегіндегі интервал статистикасы және README тәртібі

- [x] floating `QDockWidget` орнына планшет ішіндегі child overlay қолдану;
- [x] панельдің пішін еніне әсерін жою;
- [x] өлшемі мен орнын жұмыс аймағымен шектеу;
- [x] resize кезінде пайдаланушы орнын сақтап, оң жаққа қайтармау;
- [x] жабу, форма және dataset ауысу кезінде selection, shading және есепті тазалау;
- [x] тар панель үшін батырмаларды ықшамдау;
- [x] pure geometry, source-contract және Qt regression-тесттерін қосу;
- [x] түбірлік README-ден release notes пен техникалық нәтижелерді алып тастау;
- [x] README scope-test қосу;
- [ ] Windows/PySide6: DPI 100%, 125%, 150% кезінде drag/resize/close/form-switch тексеру.

Шығу шарты: панель планшет ішінде қалады, пішінді қыспайды, қолмен жылжытқаннан кейін оңға қайтпайды және форма ауысқанда толық тазаланады.

## Келесі кезеңдер

- [ ] read-only offline WITSML 2.1 inventory және mapping fixtures;
- [ ] бір пішіндегі alignment-controlled multi-dataset overlays;
- [ ] күнделікті өсімді preview арқылы растайтын directory watcher;
- [ ] fixture replay сәтті болғаннан кейін ғана secured ETP 1.2.
