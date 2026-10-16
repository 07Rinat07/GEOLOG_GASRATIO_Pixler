"""Presentation-only translations of built-in gas interpretation methodology text.

Calculation snapshots retain their original audit strings. Only known system-authored
phrases are translated; operator-entered observations are never machine-translated.
"""

from __future__ import annotations

import re

from geoworkbench.services.localization import AppLanguage


_METHOD_KK = {
    "Haworth wetness/balance/character": "Haworth: ылғалдылық, баланс және сипат",
    "Pixler hydrocarbon ratios": "Pixler: көмірсутек қатынастары",
    "Drilling-normalized C1–C5 / total gas": "Бұрғылау жағдайына нормаланған C1–C5 / жалпы газ",
    "Jorden–Shirley / Rehm–McClendon d-exponent": "Jorden–Shirley / Rehm–McClendon d-көрсеткіші",
}

_METHOD_CALCULATION_KK = {
    (
        "Wh=100×(C2+C3+ΣC4+ΣC5)/(C1+C2+C3+ΣC4+ΣC5); "
        "Bh=(C1+C2)/(C3+ΣC4+ΣC5); Ch=(ΣC4+ΣC5)/C3. "
        "The fluid label is a preliminary palette-based interpretation."
    ): (
        "Wh=100×(C2+C3+ΣC4+ΣC5)/(C1+C2+C3+ΣC4+ΣC5); "
        "Bh=(C1+C2)/(C3+ΣC4+ΣC5); Ch=(ΣC4+ΣC5)/C3. "
        "Флюид түрі палетка бойынша алдын ала бағаланады."
    ),
    (
        "C1/C2, C1/C3, C1/ΣC4 and C1/ΣC5; profile shape is supporting "
        "evidence, not a standalone productivity proof."
    ): (
        "C1/C2, C1/C3, C1/ΣC4 және C1/ΣC5 қатынастары; профиль пішіні "
        "қосымша дәлел болып саналады, бірақ өнімділікті жеке өзі растамайды."
    ),
    (
        "Each component is normalized to explicit reference drilling conditions; "
        "source and calculated normalized curves remain separate."
    ): (
        "Әр компонент нақты көрсетілген эталондық бұрғылау жағдайларына "
        "нормаланады; бастапқы және есептелген нормаланған қисықтар бөлек сақталады."
    ),
    (
        "DEXP is calculated from ROP, RPM, WOB and bit diameter; DEXPC "
        "additionally applies the explicitly supplied normal mud density."
    ): (
        "DEXP өту жылдамдығы, айналу жиілігі, қашауға түсетін жүктеме және "
        "қашау диаметрі бойынша есептеледі; DEXPC үшін көрсетілген қалыпты "
        "бұрғылау ерітіндісінің тығыздығы қосымша қолданылады."
    ),
}

# Original calculation/domain strings serve as stable keys, never as a language
# identification heuristic. The last two entries are (Kazakh, English).
_WARNINGS: dict[str, tuple[str, str]] = {
    (
        "Автоматически отмечаются только кандидаты по относительной газовой аномалии. "
        "Это не заключение о насыщении, типе флюида или промышленной продуктивности."
    ): (
        "Салыстырмалы газ аномалиясы бойынша тек болжамды аралықтар автоматты түрде "
        "белгіленеді. Бұл қанығу, флюид түрі немесе өндірістік өнімділік туралы "
        "түпкілікті қорытынды емес.",
        "Only prospective intervals based on relative gas anomalies are flagged "
        "automatically. This is not a conclusion about saturation, fluid type, "
        "or commercial productivity.",
    ),
    (
        "Предварительная интерпретация флюида сравнивает долю C2–C5 с фоном "
        "текущей скважины и применяет стандартную палетку Wh/Bh/Ch "
        "Haworth/DATALOG. ЛБА перекрывающихся проб приводится как отдельное "
        "подтверждение. Категория «вода» по mud-gas не назначается автоматически."
    ): (
        "Флюидтің алдын ала интерпретациясы C2–C5 үлесін осы ұңғыманың фондық "
        "мәнімен салыстырады және Haworth/DATALOG Wh/Bh/Ch стандартты палеткасын "
        "қолданады. Қиылысатын сынамалардағы ЛБА дербес растау дерегі ретінде "
        "беріледі. Газ каротажы бойынша «су» санаты автоматты түрде тағайындалмайды.",
        "Preliminary fluid interpretation compares the C2–C5 fraction against "
        "this well's background using the standard Haworth/DATALOG Wh/Bh/Ch "
        "palette. Fluorescence evidence from overlapping samples is reported "
        "separately. Mud-gas data alone do not automatically assign a water category.",
    ),
    (
        "Перед принятием интервалов проверьте газовый лаг, режим дегазатора, единицы, "
        "буровой режим, литологию и локально откалиброванные фоновые уровни."
    ): (
        "Аралықтарды бекітпес бұрын газдың кешігуін, дегазатор режимін, өлшем "
        "бірліктерін, бұрғылау режимін, литологияны және жергілікті фондық "
        "мәндердің калибрленуін тексеріңіз.",
        "Before accepting intervals, check gas lag, degasser operation, units, "
        "drilling conditions, lithology, and locally calibrated background levels.",
    ),
    (
        "DEXP/DEXPC используются как контекст бурения и давления, а не как "
        "самостоятельный признак углеводородов."
    ): (
        "DEXP/DEXPC көмірсутектің дербес белгісі емес, бұрғылау және қысым "
        "жағдайын бағалау үшін қолданылады.",
        "DEXP/DEXPC provide drilling and pressure context; they are not "
        "standalone hydrocarbon indicators.",
    ),
    (
        "Нормализованный газ не рассчитан. Нажмите «Рассчитать стандартные методы» "
        "и проверьте однозначное сопоставление C1–C5, ROP, BIT и FLOW с единицами."
    ): (
        "Нормаланған газ есептелмеген. «Стандартты әдістерді есептеу» пәрменін "
        "орындап, C1–C5, ROP, BIT және FLOW қисықтарының өлшем бірліктерімен "
        "сәйкестігін тексеріңіз.",
        "Normalized gas was not calculated. Run 'Calculate standard methods' "
        "and verify unambiguous C1–C5, ROP, BIT and FLOW curve/unit mapping.",
    ),
    (
        "Нет C1_NORM, TG_NORM, TG_CALC или исходного Total Gas: автоматический поиск не выполнен."
    ): (
        "C1_NORM, TG_NORM, TG_CALC немесе бастапқы Total Gas жоқ: "
        "автоматты іздеу орындалмады.",
        "C1_NORM, TG_NORM, TG_CALC or original Total Gas is missing: "
        "automatic screening was not performed.",
    ),
    "Основная газовая кривая не найдена.": (
        "Негізгі газ қисығы табылмады.",
        "The primary gas curve was not found.",
    ),
    "Основная газовая кривая имеет неверное число отсчётов.": (
        "Негізгі газ қисығындағы өлшемдер саны дұрыс емес.",
        "The primary gas curve has an invalid sample count.",
    ),
    "Для устойчивого фонового уровня требуется не менее 20 корректных газовых отсчётов.": (
        "Тұрақты фонды анықтау үшін кемінде 20 жарамды газ өлшемі қажет.",
        "At least 20 valid gas samples are required for a robust background.",
    ),
    "Газовая кривая не имеет достаточного разброса для поиска аномалий.": (
        "Газ қисығының өзгергіштігі аномалияларды іздеуге жеткіліксіз.",
        "The gas curve does not vary sufficiently for anomaly detection.",
    ),
    (
        "Режим сравнения ожидает локальный итог TG_NORM_CALC. "
        "C1_NORM не сопоставляется с серверным total normalized gas, "
        "поскольку это другой показатель. Выполните локальный расчёт."
    ): (
        "Салыстыру режимі жергілікті TG_NORM_CALC жиынтық қисығын күтеді. "
        "C1_NORM сервердегі нормаланған жалпы газбен салыстырылмайды, "
        "себебі бұл басқа көрсеткіш. Жергілікті есептеуді орындаңыз.",
        "Comparison mode requires the locally calculated total TG_NORM_CALC. "
        "C1_NORM is not compared with server normalized total gas because it is "
        "a different metric. Run the local calculation.",
    ),
}

_SOURCE_LABELS = {
    "серверная и локальная": ("серверлік және жергілікті", "server and local"),
    "серверная/файловая": ("серверлік/файлдық", "server/file"),
    "локально рассчитанная": ("жергілікті есептелген", "locally calculated"),
}
_MISSING_NORMALIZED = re.compile(
    r"^Не найдена (.+?) кривая нормализованного газа с минимум 20 корректными отсчётами\.$"
)
_IMPORTED_NORMALIZED = re.compile(
    r"^Нормализованная кривая (.+?) получена из файла/сервера и используется без "
    r"перезаписи\. Проверьте настройки оператора, формулу, эталонные условия "
    r"и единицы поставщика\.$"
)
_SERVER_CURVE = re.compile(r"^Серверная/файловая кривая (.+?) сохранена без перезаписи\.$")
_LOCAL_CURVE = re.compile(
    r"^Локальная кривая (.+?) рассчитана программой и хранится отдельно\.$"
)
_COMPARISON = re.compile(
    r"^Сравнение серверного и локального нормализованного газа выполнено по "
    r"собственному robust-фону каждой кривой: совпадающих интервалов (\d+), "
    r"только серверных (\d+), только локальных (\d+)\. "
    r"Каждый интервал отдельно сопоставлен с ЛБА\.$"
)


def localize_method_name(value: str, language: AppLanguage) -> str:
    if language is AppLanguage.KK:
        return _METHOD_KK.get(value, value)
    return value


def localize_method_calculation(value: str, language: AppLanguage) -> str:
    if language is AppLanguage.KK:
        return _METHOD_CALCULATION_KK.get(value, value)
    return value


def localize_system_warning(value: str, language: AppLanguage) -> str:
    """Localize authored diagnostics while leaving unknown/source prose unchanged."""
    if language is AppLanguage.RU:
        return value

    position = 0 if language is AppLanguage.KK else 1
    if (translated := _WARNINGS.get(value)) is not None:
        return translated[position]

    if (match := _MISSING_NORMALIZED.fullmatch(value)) is not None:
        label = _SOURCE_LABELS.get(match.group(1))
        if label is not None:
            rendered_label = label[position]
            return (
                f"Кемінде 20 жарамды өлшемі бар {rendered_label} нормаланған газ қисығы табылмады."
                if language is AppLanguage.KK
                else f"No {rendered_label} normalized gas curve with at least 20 valid samples was found."
            )
    if (match := _IMPORTED_NORMALIZED.fullmatch(value)) is not None:
        name = match.group(1)
        return (
            f"{name} нормаланған қисығы файлдан/серверден алынып, өзгеріссіз пайдаланылды. "
            "Оператор параметрлерін, формуланы, эталондық жағдайларды және өлшем бірліктерін тексеріңіз."
            if language is AppLanguage.KK
            else f"Normalized curve {name} came from a file/server and is used without modification. "
            "Verify operator settings, formula, reference conditions and supplier units."
        )
    if (match := _SERVER_CURVE.fullmatch(value)) is not None:
        return (
            f"Серверлік/файлдық {match.group(1)} қисығы өзгеріссіз сақталды."
            if language is AppLanguage.KK
            else f"Server/file curve {match.group(1)} was preserved without modification."
        )
    if (match := _LOCAL_CURVE.fullmatch(value)) is not None:
        return (
            f"Жергілікті {match.group(1)} қисығы бағдарламамен есептеліп, бөлек сақталды."
            if language is AppLanguage.KK
            else f"Local curve {match.group(1)} was calculated by the application and stored separately."
        )
    if (match := _COMPARISON.fullmatch(value)) is not None:
        same, server_only, local_only = match.groups()
        return (
            "Серверлік және жергілікті нормаланған газ әр қисықтың жеке robust-фоны бойынша "
            f"салыстырылды: сәйкес аралықтар {same}, тек серверлік {server_only}, "
            f"тек жергілікті {local_only}. Әр аралық ЛБА деректерімен жеке салыстырылды."
            if language is AppLanguage.KK
            else "Server and local normalized gas were compared using each curve's own robust "
            f"background: matched intervals {same}, server-only {server_only}, "
            f"local-only {local_only}. Each interval was separately compared with fluorescence data."
        )

    # Per-curve diagnostic: the mnemonic/source marker is data, but the suffix
    # is a known system warning and can be localized without changing provenance.
    prefix, separator, detail = value.partition(": ")
    if separator and prefix.endswith((" (server)", " (local-calculation)")):
        localized = localize_system_warning(detail, language)
        if localized != detail:
            return f"{prefix}: {localized}"
    return value


# Detector evidence is stored as immutable engineering/audit data. Translate only
# the two literal labels generated by _detect_candidates; do not parse/round values.
_DETECTOR_ROBUST_Z = re.compile(
    r"^max robust z = ([0-9.+-]+) [(]threshold ([0-9.+-]+)[)]$"
)
_DETECTOR_MAX = re.compile(r"^max = ([0-9.eE+-]+)$")


def localize_detector_metric(value: str, language: AppLanguage) -> str:
    """Translate the auto-generated metric label, preserving numeric audit text."""
    if (match := _DETECTOR_ROBUST_Z.fullmatch(value)) is not None:
        peak, threshold = match.groups()
        return {
            AppLanguage.RU: f"максимальный robust z = {peak} (порог {threshold})",
            AppLanguage.KK: f"robust z ең жоғары мәні = {peak} (шек {threshold})",
            AppLanguage.EN: value,
        }[language]
    if (match := _DETECTOR_MAX.fullmatch(value)) is not None:
        peak = match.group(1)
        return {
            AppLanguage.RU: f"максимум = {peak}",
            AppLanguage.KK: f"ең жоғары мән = {peak}",
            AppLanguage.EN: value,
        }[language]
    return value


__all__ = [
    "localize_detector_metric",
    "localize_method_calculation",
    "localize_method_name",
    "localize_system_warning",
]
