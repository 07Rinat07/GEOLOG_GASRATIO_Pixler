
## Граница WITS0 reliability — 0.7.78

`wits0_reliability.py` отвечает за disk policy, retention, sidecar recovery, atomic manifest,
append-only connection journal и workspace codec без зависимости от Qt. Capture проверяет диск до
raw write и защищает активный сегмент. Connection/disconnection попадают в открытую сессию только
как typed records через bounded `AcquisitionController`.

Restart recovery использует persisted immutable schema и versioned custom profile, а не
восстанавливает вымышленные discovery statistics. `.wits` не переписывается; исправляется только
недостоверный хвост JSONL sidecar. `QSettings` содержит только состояние представления.
