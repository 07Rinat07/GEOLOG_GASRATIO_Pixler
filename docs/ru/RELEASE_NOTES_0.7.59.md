# GEOLOG GASRATIO@Pixler 0.7.59

Критический hotfix переключения форм. Плотные колонки с внутренней прокруткой шапки обращались к отсутствующему `TabletTrackWidget._localizer`, поэтому применение формы падало и запускался откат. Теперь каждый track получает активный localizer до заполнения шапки, а прямое создание использует безопасный fallback. Project format v20, form schema v6 и tablet layout v16 не изменялись.
