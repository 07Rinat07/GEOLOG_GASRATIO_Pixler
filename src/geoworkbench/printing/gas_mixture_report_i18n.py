from __future__ import annotations

from geoworkbench.services.localization import AppLanguage


_RAMP_WARNINGS = {
    'screening': {
        AppLanguage.RU: 'Результат является скрининговой интерпретацией отклика C1–C5. Он не заменяет калиброванный лабораторный анализ состава пробы.',
        AppLanguage.KK: 'Нәтиже C1–C5 жауабының скринингтік интерпретациясы болып табылады. Ол сынама құрамының калибрленген зертханалық талдауын алмастырмайды.',
        AppLanguage.EN: 'This result is a screening interpretation of the C1–C5 response. It does not replace calibrated laboratory analysis of the sample composition.',
    },
    'water': {
        AppLanguage.RU: 'Категория «вода» по одному отклику углеводородных газов не назначается; низкий сигнал обозначается как фон/недостаточно данных.',
        AppLanguage.KK: 'Көмірсутек газдарының жауабы бойынша ғана «су» санаты тағайындалмайды; төмен сигнал фон/деректер жеткіліксіз деп белгіленеді.',
        AppLanguage.EN: 'The water category is not assigned from the hydrocarbon-gas response alone; a low signal is reported as background/insufficient data.',
    },
    'calibration': {
        AppLanguage.RU: 'Для количественных молярных долей нужны калибровка газоанализатора, контроль нуля/стандарта и оценка неопределённости.',
        AppLanguage.KK: 'Сандық мольдік үлестер үшін газ талдағышын калибрлеу, нөлді/стандартты бақылау және белгісіздікті бағалау қажет.',
        AppLanguage.EN: 'Quantitative mole fractions require gas-analyzer calibration, zero/standard checks and an uncertainty assessment.',
    },
    'background': {
        AppLanguage.RU: 'Фоновый уровень каждого компонента оценён по нижнему квантилю временного отклика и вычтен только для расчёта состава; на диаграмме показан исходный отклик.',
        AppLanguage.KK: 'Әр компоненттің фондық деңгейі уақыттық жауаптың төменгі квантилі бойынша бағаланып, тек құрамды есептеу үшін алынады; диаграммада бастапқы жауап көрсетіледі.',
        AppLanguage.EN: 'Each component background is estimated from the lower quantile of the time response and subtracted only for composition calculations; the chart shows the original response.',
    },
    'missing_time': {
        AppLanguage.RU: 'В наборе нет временной оси; график построен по порядковому номеру отсчёта.',
        AppLanguage.KK: 'Деректер жинағында уақыт осі жоқ; график өлшемнің реттік нөмірі бойынша құрылған.',
        AppLanguage.EN: 'The dataset has no time axis; the chart uses the sample sequence number.',
    },
}


def ramp_standard_warnings() -> tuple[str, ...]:
    """Retain the existing audit strings independently of presentation language."""
    return tuple(values[AppLanguage.RU] for key, values in _RAMP_WARNINGS.items() if key != 'missing_time')


def ramp_missing_time_warning() -> str:
    return _RAMP_WARNINGS['missing_time'][AppLanguage.RU]


def localized_ramp_warnings(warnings: tuple[str, ...], language: AppLanguage) -> tuple[str, ...]:
    # Translate only known generated messages; caller/vendor text remains verbatim.
    translations = {values[AppLanguage.RU]: values[language] for values in _RAMP_WARNINGS.values()}
    return tuple(translations.get(value, value) for value in warnings)


def localized_ramp_time_label(label: str, language: AppLanguage) -> str:
    return {
        '№ отсчёта': {AppLanguage.RU:'№ отсчёта', AppLanguage.KK:'Өлшем №', AppLanguage.EN:'Sample number'},
        'Время от начала, с': {AppLanguage.RU:'Время от начала, с', AppLanguage.KK:'Басталғаннан бергі уақыт, с', AppLanguage.EN:'Elapsed time, s'},
    }.get(label, {}).get(language, label)
