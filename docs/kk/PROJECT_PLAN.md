# Жоба жоспары

2026 жылғы 24 шілдеге өзекті. **0.7.59** hotfix project format v20, form schema v6 және tablet layout v16 сақтайды.

## P0 — hotfix 0.7.59: тығыз localized пішіндерді қауіпсіз ауыстыру

- [x] әр `TabletTrackWidget` ішінде localizer инициализациялау;
- [x] `TabletView` белсенді localizer-ін барлық жаңа track-ке беру;
- [x] test/plugin арқылы тікелей жасалған widget үшін fallback сақтау;
- [x] track creation boundary үшін source-contract тест қосу;
- [x] жеті параметрлі форма және overflow tooltip үшін Qt regression тест қосу;
- [x] status, changelog, testing және RU/KK/EN release notes синхрондау;
- [ ] Windows/PySide6: RU/KK/EN тілдерінде тығыз пішіндерді бірнеше рет ауыстырып, rollback тексеру.

Шығу шарты: ішкі scroll бар тақырыпты пішін `AttributeError`-сыз қолданылады, ал басқа қате кезінде алдыңғы жұмыс істейтін пішін сақталады.

## Келесі кезеңдер

- [ ] read-only offline WITSML 2.1 inventory және mapping fixtures;
- [ ] бір пішіндегі alignment-controlled multi-dataset overlays;
- [ ] күнделікті өсімді preview арқылы растайтын directory watcher;
- [ ] fixture replay сәтті болғаннан кейін ғана secured ETP 1.2.
