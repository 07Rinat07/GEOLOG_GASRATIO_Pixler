# 0.7.42 шығарылым ескертпелері — append-only acquisition және replay

- immutable dataset schema бар persisted acquisition session қосылды;
- rows және operational events үздіксіз append-only journal ішінде жазылады;
- bounded buffer, backpressure, atomic rollback және controlled close іске асырылды;
- checkpoints row count, dataset/events projection және combined audit digest сақтайды;
- нөлден немесе verified checkpoint-тен replay rows, events, QC және есепті транзакциялық түрде қайталап, metadata тексереді;
- project format v18-ге көтерілді және қауіпсіз v17 → v18 migration қосылды;
- келесі срез — source journal-ды өзгертпейтін versioned lag/depth correction.

Тексеру: 127 focused tests passed; headless: 952 passed, 4 skipped, 3 deselected.
