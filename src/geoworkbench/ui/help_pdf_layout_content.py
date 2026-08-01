from __future__ import annotations

from geoworkbench.services.localization import AppLanguage


_PDF_LAYOUT_HELP = {
    AppLanguage.RU: """
        <h2>Постраничный график газового каротажа</h2>
        <ul>
          <li>PDF-экспорт и системная печать используют один постраничный движок.</li>
          <li>Вертикальный масштаб выбирается автоматически из стандартного ряда
              и указывается на каждом графическом листе.</li>
          <li>Короткая скважина не растягивается искусственно, а длинная делится
              на непрерывные последовательные диапазоны глубины.</li>
          <li>На каждом листе повторяются левая и правая шкалы глубины, внешние
              границы, заголовки дорожек, легенда и диапазон листа.</li>
          <li>Кривые печатаются векторно. Таблицы переносятся только между
              строками, а шапка повторяется на странице продолжения.</li>
          <li>Перед печатью проверьте первую и последнюю графические страницы,
              правую шкалу, легенду, примечание и страницы продолжения таблиц.</li>
        </ul>
    """,
    AppLanguage.KK: """
        <h2>Газ каротажының көпбетті графигі</h2>
        <ul>
          <li>PDF экспорты мен жүйелік басып шығару бір көпбетті қозғалтқышты пайдаланады.</li>
          <li>Тік масштаб стандартты қатардан автоматты түрде таңдалып, әр
              график бетінде көрсетіледі.</li>
          <li>Қысқа ұңғыма жасанды созылмайды, ал ұзын ұңғыма тереңдіктің
              үздіксіз және ретімен жалғасатын аралықтарына бөлінеді.</li>
          <li>Әр бетте сол және оң тереңдік шкалалары, сыртқы шекаралар, жол
              тақырыптары, шартты белгілер және бет аралығы қайталанады.</li>
          <li>Қисықтар векторлық түрде басылады. Кестелер тек жолдар арасында
              тасымалданады, ал кесте тақырыбы жалғастыру бетінде қайталанады.</li>
          <li>Басып шығару алдында бірінші және соңғы график бетін, оң шкаланы,
              шартты белгілерді, ескертпені және кесте жалғасын тексеріңіз.</li>
        </ul>
    """,
    AppLanguage.EN: """
        <h2>Multi-page mud-gas chart</h2>
        <ul>
          <li>PDF export and system printing use the same controlled renderer.</li>
          <li>The vertical scale is selected automatically from a standard series
              and printed on every chart sheet.</li>
          <li>A short well is not stretched artificially; a long well is divided
              into continuous, sequential depth ranges.</li>
          <li>Every sheet repeats the left and right depth scales, outer borders,
              track headings, legend, and sheet range.</li>
          <li>Curves are printed as vector graphics. Tables continue only between
              rows, and the table header repeats on continuation pages.</li>
          <li>Before printing, inspect the first and last chart sheets, the right
              scale, legend, note, and all table continuation pages.</li>
        </ul>
    """,
}


def pdf_layout_help_html(language: AppLanguage) -> str:
    return _PDF_LAYOUT_HELP[language]


def append_pdf_layout_help(html: str, language: AppLanguage) -> str:
    return html + pdf_layout_help_html(language)


__all__ = ["append_pdf_layout_help", "pdf_layout_help_html"]
