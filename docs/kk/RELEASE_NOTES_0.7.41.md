# 0.7.41 шығарылым ескертпелері — типтелген operational events

- drilling, gas, show, sample, casing және formation-top үшін қатаң payload models қосылды;
- depth/time anchors, source, revision, calibration және QC flags бар ортақ envelope қосылды;
- duplicate, out-of-order, gap, stale және calibration QC детерминирленген түрде іске асырылды;
- optimistic revision және cross-well қорғанысы бар `OperationalEventController` қосылды;
- project format v17-ге көтерілді, v16 → v17 қауіпсіз migration бос collection қосады;
- codec discriminator бойынша payload-ты қалпына келтіріп, бұзылған fields-ті қабылдамайды;
- EVENTS/DRILLING нақты `ResolvedReportDefinition` аралығына қайта resolve жасамай қосылды;
- `ui` ішіндегі ескірген import-controller көшірмелері жойылды, белсенді boundary `services` ішінде қалды;
- headless domain, controller, QC, migration, codec және report tests қосылды;
- plan, status, changelog және RU/KK/EN guides синхрондалды.

Толық Ruff/mypy/Qt/LAS gate және Windows smoke-test өткенше жинақ тесттік болып қалады.
