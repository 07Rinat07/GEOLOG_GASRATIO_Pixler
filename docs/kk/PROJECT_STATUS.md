# Жоба күйі

2026 жылғы 24 шілдедегі түзету жинағы: package **0.7.51**, тұрақты runtime диагностикасы және
қауіпсіз қарындаш/пішін lifecycle. Project format: **v20**, form schema: **v6**, tablet layout:
**v16**.

## 0.7.51 ішінде аяқталды

- қолданба айналмалы `geolog.log` және бөлек `geolog-crash.log` файлдарын жүргізеді;
- ұсталмаған Python/thread exceptions, Qt messages және Qt event-handler қателері жазылады;
- form apply/rollback, толық tablet render және curve-pencil commit тұрақты оқиға кодтары мен
  толық traceback қолданады;
- «Анықтама» мәзірі журнал бумасын ашады, жолды көшіреді және diagnostics ZIP құрады;
- diagnostics bundle LAS мәндерін, datasets, пішіндер мен project assets қоспайды;
- қарындаш commit тек өзгерген және қайта есептелген curve tracks жаңартады;
- шапканың автоматты диапазондары қолданыстағы редакторларды жоймай орнында жаңартылады;
- әр штрихтан кейін планшет толық қайта құрылмайды, сондықтан пішін, ендер және көлденең орын
  сақталады;
- толық form rebuild алдында pencil mode, preview және stale track/curve targets тазартылады;
- candidate form алдымен тексеріліп, содан кейін ғана виджеттер ауыстырылады;
- apply/rollback қателері журналға жазылады, ал rollback тек модельден қайта құрылады.

## Тексеру

- focused logging/form/pencil/tablet suite: **245 passed**;
- қолжетімді headless regression: **1048 passed, 4 skipped, 4 deselected**;
- `compileall` сәтті;
- Windows PySide6 smoke-test міндетті: нақты сурет салу, Undo/Redo, штрихтан кейін пішін ауыстыру
  және diagnostics ZIP құру.

## Келесі vertical slice

Read-only offline WITSML 2.1 inventory және mapping fixtures. ETP 1.2 fixture replay орындалғанға
дейін жабық.
