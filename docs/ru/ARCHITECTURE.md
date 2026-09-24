
## Граница WITS0 reliability — 0.7.78

`wits0_reliability.py` отвечает за disk policy, retention, sidecar recovery, atomic manifest,
append-only connection journal и workspace codec без зависимости от Qt. Capture проверяет диск до
raw write и защищает активный сегмент. Connection/disconnection попадают в открытую сессию только
как typed records через bounded `AcquisitionController`.

Restart recovery использует persisted immutable schema и versioned custom profile, а не
восстанавливает вымышленные discovery statistics. `.wits` не переписывается; исправляется только
недостоверный хвост JSONL sidecar. `QSettings` содержит только состояние представления.

SEC-04 разрешает destructive retention только при действительном path-bound marker владения приложения. Non-loopback server допустим только после подтверждённого предупреждения и с non-global IPv4 CIDR allowlist; sockets от peers вне политики закрываются до raw capture и журналируются как rejected.


## WITS0 operator workspace — 0.7.96+

Live WITS UI не владеет расчётными формулами. Gas Ratio/Pixler/DEXP используют существующий
versioned calculation registry и общий UOM dictionary; gas-origin classification и threshold alarms
реализуются отдельными headless services. Qt отвечает за формы, fullscreen, badges, help и
audio/visual presentation. Сохранённые формы используют canonical mnemonic вместо curve_id.
Fluid screening, gas origin и threshold alarm остаются независимыми событиями.
