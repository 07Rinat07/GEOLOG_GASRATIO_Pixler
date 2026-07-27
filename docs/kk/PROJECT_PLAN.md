# Жоба жоспары

0.7.79 кезеңінен кейін 2026 жылғы 27 шілдеге өзекті. Бұл файлда тек аяқталмаған жұмыс берілген;
орындалған кезеңдер project status, changelog және release notes ішінде көрсетіледі.

## Басымдық: WITS0 далалық қабылдауы

Raw capture, parser, Import Review, normalized batches, append-only session, live monitor және
software reliability қабаты дайын. Қалған жұмыс:

- [ ] нақты анонимделген GSWITS raw ағынының 5–10 минутын алу;
- [ ] TCP mode, address, port, encoding, headers және record interval мәндерін растау;
- [ ] built-in және custom GeoScape profile-дарын нақты record/item арқылы тексеру;
- [ ] нақты GSWITS-пен 8–24 сағаттық Windows soak өткізіп, JSON есепті сақтау;
- [ ] GSWITS, қолданба және Windows қайта іске қосылғаннан кейін reconnect тексеру;
- [ ] raw жоғалтпай бақыланатын low-space/disk-full тестін орындау;
- [ ] Windows startup/service strategy және signed field checklist анықтау;
- [ ] сәйкес емес өлшем бірліктері үшін тәуелсіз track/scale қосу;
- [ ] жабылған сессиядан кейін жаңа source session саясатын анықтау.

## 0.7.79 ішінде аяқталды: WITSML offline data import

- [x] `ChannelSet`, белсенді `Index` және scalar numeric `Channel` таңдау;
- [x] network ETP қолданбай embedded Data және қауіпсіз relative FileUri оқу;
- [x] time/depth index және Well/Wellbore metadata байланыстыру;
- [x] сандық conversion бар Semantic Channel Dictionary/UOM Import Review;
- [x] immutable Dataset-ті атомарлық құру және тіркеу;
- [x] анық provenance және regression tests бар синтетикалық fixture.

## Келесі өнімдік кезең: WITSML 1.4.1.1 SOAP read-only

- [ ] GetVersion/GetCap және read-only Well → Wellbore → Log → LogData;
- [ ] credentials-ті project file сыртында сақтау;
- [ ] Add/Update/Delete қолданбай timeout/retry/audit қосу.

## Қабылдау критерийі

Бір нақты GSWITS ағыны reconnect, view pause, project save, crash restart және low-space boundary
жағдайларынан өтуі тиіс; raw bytes, connection journal, recovery manifest, acquisition session,
checkpoints және Dataset projection келісімді қалуы керек.
