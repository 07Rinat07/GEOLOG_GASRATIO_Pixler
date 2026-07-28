
## WITS0 reliability шекарасы — 0.7.78

`wits0_reliability.py` Qt тәуелділігінсіз disk policy, retention, sidecar recovery, atomic manifest,
append-only connection journal және workspace codec үшін жауап береді. Capture raw write алдында
дискіні тексереді және белсенді сегментті қорғайды. Connection шекаралары ашық session ішіне тек
bounded `AcquisitionController` арқылы типтелген records ретінде түседі.

Restart recovery persisted immutable schema және versioned custom profile қолданады; discovery
statistics ойдан жасалмайды. `.wits` байттары өзгермейді, тек сенімсіз JSONL sidecar соңы атомарлы
алынады. `QSettings` тек presentation state сақтайды.

SEC-04 destructive retention-ды тек қолданбаның жарамды path-bound ownership marker-і болғанда рұқсат етеді. Non-loopback server қауіпсіздік ескертуі расталып, non-global IPv4 CIDR peer allowlist берілгенде ғана жарамды; саясаттан тыс peers sockets raw capture басталмай тұрып жабылып, rejected ретінде journal-ға жазылады.
