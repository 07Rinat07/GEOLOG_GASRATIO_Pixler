# Жоба жоспары

2026 жылғы 24 шілдедегі күй. **0.7.52** hotfix project format v20, form schema v6 және tablet
layout v16 сақтайды. Windows тексеруінен кейінгі келесі кезең — read-only offline WITSML 2.1
inventory және mapping fixtures.

## P0 — hotfix 0.7.52: идемпотентті Qt тазалау және ықшам тақырыптар

- [x] QObject wrapper-ді `shiboken6.isValid()` арқылы тексеру;
- [x] event filter және `deleteLater()` қауіпсіз орындау;
- [x] бір wrapper қатесінен кейін қалған тректерді тазалауды жалғастыру;
- [x] қайталама tablet reset-ті қауіпсіз ету;
- [x] жойылған `CurveHeaderEditor` import recovery/rollback-ты бөгемеу;
- [x] өңделетін тақырыпты 52 px, қарапайым белгіні 38 px ету;
- [x] min/unit/max және linear/log тікелей өңдеуін сақтау;
- [x] сызғышты сақталған grid divisions-пен сәйкестендіру және ортақ жолақты 360 px ету;
- [x] LAS duplicate/irregular-step/gap үшін нақты ұсыныстар қосу;
- [x] cleanup/header/diagnostics contract тесттерін қосу;
- [ ] Windows/PySide6: проблемалық LAS, 20 form switch, 20 reset және 100/125/150% DPI.

Шығу критерийі: импортталған дерек қолжетімді қалады, тазалау жойылған widget-те құламайды және
шкала мен бірлік сақталып, тақырып айтарлықтай ықшам болады.

## Келесі кезеңдер

- [ ] read-only offline WITSML 2.1 inventory және mapping fixtures;
- [ ] бір пішіндегі alignment-controlled multi-dataset overlays;
- [ ] күнделікті өсімге preview-confirmation бар directory watcher;
- [ ] fixture replay сәтті болғаннан кейін ғана secured ETP 1.2.
