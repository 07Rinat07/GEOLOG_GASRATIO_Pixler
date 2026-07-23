# Жоба күйі

Кесім: 2026 жылғы 23 шілде. 0.7.32 нұсқасы, тест жинағы.

## Шығарылым шешімі

Соңғы толық 0.7.28 baseline жасыл: Ruff өтті, mypy 262 бастапқы файлда 0 қате көрсетті,
толық pytest нәтижесі — 1217 өтті және 10 өткізіліп жіберілді. 0.7.32 үшін `compileall`, wheel
жинағы және қолжетімді headless regression орындалды: 707 тест өтті, 4 платформалық сценарий
өткізіліп жіберілді. Толық pytest жинауы 95 Qt/LAS тәуелді модульде тоқтайды, себебі контейнерде
PySide6, pyqtgraph және lasio жоқ; Ruff пен mypy де қолжетімсіз. Толық gate және
Windows/HiDPI/PDF/физикалық баспа тексерілгенше жинақ тест күйінде қалады.

## Жұмыс істейтін негіз

- LAS/CSV/TXT/Excel/Paradox үшін қауіпсіз import және edit сценарийлері;
- бірнеше dataset және индексі бар project format v16;
- бірыңғай Semantic Channel Dictionary және анық UOM quantity-class dictionary;
- бастапқы mnemonic, source UOM, sensor, confidence және evidence сақтайтын curve binding;
- index, NULL, unresolved, UOM conflict және duplicate үшін read-only Import Review;
- көп жолақты планшет, forms, Masterlog, PDF, Print Center, annotations және project assets;
- синхронды RU/KK/EN пайдаланушы құжаттары.

Semantic binding CSV/Excel, LAS және Paradox үшін бірдей жасалады және copy, merge, resample,
TIME↔DEPTH кезінде сақталады. Ескі жобалар оқылғанда бұрынғы canonical mnemonic өзгертілмейді.

Келесі кезең — manual overrides және атомарлық растауы бар интерактивті Import Review.

Толығырақ: [Semantic Channel Dictionary](SEMANTIC_CHANNEL_DICTIONARY.md),
[аудит](PRODUCT_AUDIT_2026.md) және [жоспар](PROJECT_PLAN.md).
