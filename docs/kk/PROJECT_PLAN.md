# Жоба жоспары

2026 жылғы 24 шілдедегі күй. 0.7.49 түзету срезі project format v20, form schema v6 және
tablet layout v16 мәндерін сақтайды. Windows тексерісінен кейінгі келесі domain slice —
read-only offline WITSML 2.1 inventory және mapping fixtures.

## P0 — 0.7.49 hotfix: сенімді шкала және қауіпсіз пішіндер

- [x] жаңа және автоматты жасалған қисықтар үшін linear scale әдепкі ету;
- [x] manual range графиктің өзін өзгертуі үшін scale/minimum/maximum render key құрамына енгізу;
- [x] дұрыс диапазонды debounce кейін немесе Enter арқылы бірден қолдану;
- [x] графикалық баған тарылғанда minimum және maximum өрістерін жоғалтпау;
- [x] unit және linear/logarithmic selector-ды бөлек responsive қатарға орналастыру;
- [x] engineering ruler мен grid major/minor divisions сәйкестігін сақтау;
- [x] жаңа пішінді project session commit алдында толық render жасау;
- [x] қате кезінде соңғы жұмыс пішінін, dirty marker және selection күйін қайтару;
- [x] Form Manager Cancel кезінде live preview-ды rollback жасау;
- [x] қауіпсіз қолданылмаған пішінді print-ке жібермеу;
- [x] render-before-commit, rollback және range үшін headless tests қосу;
- [ ] Windows/PySide6/HiDPI ішінде тар баған, manual range және rollback smoke-test орындау.

0.7.49 критерийі: minimum/maximum өзгерісі қисықты көрінетін түрде қайта салады; тар бағанда екі
шек қолжетімді; сәтсіз form switch немесе preview Cancel планшетті жартылай өзгерген күйде
қалдырмайды.

## Келесі кезеңдер

- [ ] read-only offline WITSML 2.1 inventory және mapping fixtures;
- [ ] бір пішіндегі alignment-controlled multi-dataset overlays;
- [ ] күнделікті өсімге preview растауы бар directory watcher;
- [ ] fixture replay өткеннен кейін ғана secured ETP 1.2.
