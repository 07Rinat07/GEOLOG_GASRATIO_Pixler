# Жоба күйі

Кесім: 2026 жылғы 23 шілде. Нұсқа: 0.7.43, тесттік жинақ.

## Орындалды

- сәлемдесу терезесі блоктайтын `sleep` қолданбай кемінде 3000 мс көрсетіліп, кейін 180 мс ішінде бірқалыпты өшеді;
- project format v18 және қауіпсіз v17 → v18 migration;
- `well.acquisition_sessions` ішіндегі persisted acquisition schema v1;
- immutable index/curve schema және append-only `DATA_ROW`, `EVENT_UPSERT`, `EVENT_DELETE`;
- үздіксіз sequence, bounded buffer және record жоғалтпайтын нақты backpressure;
- apply қатесінде dataset/events/journal атомарлы rollback;
- row count және dataset/events/audit SHA-256 бар checkpoints;
- нөлден немесе verified checkpoint-тен deterministic replay;
- replay соңында бірдей rows, operational events, QC flags және report projection;
- final checkpoint және final audit digest бар жабық session.

Мақсатты startup/version жинағы: 13 passed. Қолжетімді headless regression: 964 passed,
4 skipped, `lasio` жоқ болғандықтан 3 deselected. Толық Qt/LAS/Ruff/mypy gate және
Windows/HiDPI/PDF/physical-print smoke-test міндетті болып қалады.

Келесі кесім: append-only source-ты өзгертпейтін versioned lag/depth correction.

[Acquisition replay](ACQUISITION_REPLAY.md) және [жалпы күй](../PROJECT_STATUS.md).
