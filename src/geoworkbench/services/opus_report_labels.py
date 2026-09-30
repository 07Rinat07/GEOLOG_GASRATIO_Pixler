"""Presentation labels; stored OPUS codes and calculation evidence stay unchanged."""

from geoworkbench.services.localization import AppLanguage


_LABELS = {
    "title": ("ОПУС Газомер — пять показателей и голоса", "ОПУС Газомер — бес көрсеткіш және дауыстар", "OPUS Gasomer — five indicators and votes"),
    "profile": ("Профиль", "Профиль", "Profile"),
    "status": ("статус", "мәртебе", "status"),
    "mode": ("Режим", "Режим", "Mode"),
    "source": ("источник интервалов", "аралықтар көзі", "interval source"),
    "unit": ("рабочая единица", "жұмыс бірлігі", "working unit"),
    "inputs": ("Входные кривые", "Кіріс қисықтар", "Input curves"),
    "indicator": ("Показатель", "Көрсеткіш", "Indicator"),
    "formula": ("Точная формула профиля", "Профильдің нақты формуласы", "Exact profile formula"),
    "median": ("Медиана", "Медиана", "Median"),
    "vote": ("Голос", "Дауыс", "Vote"),
    "vote_support": ("Поддержка голоса", "Дауыс қолдауы", "Vote support"),
    "available_header": ("Доступно", "Қолжетімді", "Available"),
    "votes": ("Голоса 1–7", "1–7 дауыстары", "Votes 1–7"),
    "qc": ("QC-состояния", "QC күйлері", "QC states"),
    "class": ("класс", "сынып", "class"),
    "support": ("Поддержка класса", "Сынып қолдауы", "Class support"),
    "rows": ("валидных синхронных строк", "жарамды синхронды жолдар", "valid synchronous rows"),
    "background": ("локальный фон", "жергілікті фон", "local background"),
    "peak": ("пик", "шың", "peak"),
    "contrast": ("контраст", "контраст", "contrast"),
    "lod_missing": ("не задан; детектор не запускается без явного значения", "берілмеген; нақты мәнсіз детектор іске қосылмайды", "not set; the detector requires an explicit value"),
    "empty": ("Интервалы ОПУС Газомер не сформированы: проверьте независимый TotalGas, C1–C5, единицы и положительный LOD TotalGas.", "ОПУС Газомер аралықтары құрылмады: тәуелсіз TotalGas, C1–C5, бірліктерді және оң LOD TotalGas мәнін тексеріңіз.", "No OPUS Gasomer intervals: check independent TotalGas, C1–C5, units and a positive TotalGas LOD."),
    "provenance": ("Происхождение формул", "Формулалардың шығу тегі", "Formula provenance"),
    "hash": ("SHA-256 книги", "Жұмыс кітабының SHA-256 мәні", "Workbook SHA-256"),
    "errata": ("Исправления исходной книги", "Бастапқы жұмыс кітабының түзетулері", "Source workbook errata"),
    "AVAILABLE": ("доступно", "қолжетімді", "available"),
    "MISSING": ("нет данных", "деректер жоқ", "missing"),
    "MEASURED_ZERO": ("измеренный ноль", "өлшенген нөл", "measured zero"),
    "BELOW_LOD": ("ниже LOD", "LOD-тан төмен", "below LOD"),
    "INVALID": ("некорректно", "жарамсыз", "invalid"),
    "class_1": ("Признаки окисленной/остаточной нефтяной фазы", "Тотыққан/қалдық мұнай фазасының белгілері", "Indications of an oxidized/residual-oil phase"),
    "class_2": ("Признаки нефтяной фазы", "Мұнай фазасының белгілері", "Indications of an oil phase"),
    "class_3": ("Газовая УВ-фаза (горючий газ)", "Газдық КС фазасы (жанғыш газ)", "Gaseous hydrocarbon phase (combustible gas)"),
    "class_4": ("Водорастворённый газ", "Суда еріген газ", "Water-dissolved gas"),
    "class_5": ("Газоконденсатная УВ-фаза", "Газ-конденсатты КС фазасы", "Gas-condensate hydrocarbon phase"),
    "class_6": ("Признаки газированной нефтяной фазы", "Газдалған мұнай фазасының белгілері", "Indications of a gassy-oil phase"),
    "class_7": ("УВ-флюид неопределённого типа", "Түрі анықталмаған көмірсутекті флюид", "Hydrocarbon fluid of undetermined type"),
}


def opus_report_label(key: str, language: AppLanguage) -> str:
    values = _LABELS.get(key) or _LABELS.get(key.upper())
    if values is None:
        return key
    return values[{AppLanguage.RU: 0, AppLanguage.KK: 1, AppLanguage.EN: 2}[language]]
