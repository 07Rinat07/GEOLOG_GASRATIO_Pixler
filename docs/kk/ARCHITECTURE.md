
## WITS0 reliability шекарасы — 0.7.78

`wits0_reliability.py` Qt тәуелділігінсіз disk policy, retention, sidecar recovery, atomic manifest,
append-only connection journal және workspace codec үшін жауап береді. Capture raw write алдында
дискіні тексереді және белсенді сегментті қорғайды. Connection шекаралары ашық session ішіне тек
bounded `AcquisitionController` арқылы типтелген records ретінде түседі.

Restart recovery persisted immutable schema және versioned custom profile қолданады; discovery
statistics ойдан жасалмайды. `.wits` байттары өзгермейді, тек сенімсіз JSONL sidecar соңы атомарлы
алынады. `QSettings` тек presentation state сақтайды.
