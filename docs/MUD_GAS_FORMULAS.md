# Формулы анализа бурового газа

## Реализованные зависимости

Обозначения: `ΣC4 = iC4 + nC4`, `ΣC5 = iC5 + nC5`.

```text
Wh = 100 × (C2 + C3 + ΣC4 + ΣC5) / (C1 + C2 + C3 + ΣC4 + ΣC5)
Bh = (C1 + C2) / (C3 + ΣC4 + ΣC5)
Ch = (ΣC4 + ΣC5) / C3

Pixler: C1/C2, C1/C3, C1/ΣC4, C1/ΣC5
```

Все компоненты должны иметь одинаковые единицы концентрации. Нулевой или
нечисловой знаменатель даёт `NaN`, а не бесконечность. Формулы выполняют
предварительный инженерный расчёт и сами по себе не доказывают тип флюида:
результат необходимо сопоставлять с качеством отбора газа, режимом бурения,
литологией, фоном, ГИС и испытаниями.

## Первичные источники

1. Haworth, J. H., Sellens, M., Whittaker, A. (1985). *Interpretation of
   Hydrocarbon Shows Using Light (C1-C5) Hydrocarbon Gases from Mud-Log Data*.
   AAPG Bulletin, 69(8), 1305-1310.
   [Официальная карточка AAPG](https://archives.datapages.com/data/bulletns/1984-85/data/pg/0069/0008/1300/1305.htm).
2. Pixler, B. O. (1969). *Formation Evaluation by Analysis of Hydrocarbon
   Ratios*. Journal of Petroleum Technology, 21(6), 665-670.
   [DOI: 10.2118/2254-PA](https://doi.org/10.2118/2254-PA).

Полные тексты этих публикаций не включены: страницы издателей не предоставляют
их для свободного распространения.

## Открытый обзор

Muriungi, N. (2025). *Application of mud gas analysis for reservoir evaluation*.
EarthArXiv, DOI [10.31223/X55F0F](https://doi.org/10.31223/X55F0F), лицензия
CC BY 4.0. Локальная копия официального препринта:
[`resources/literature/muriungi-2025-mud-gas-analysis.pdf`](../resources/literature/muriungi-2025-mud-gas-analysis.pdf).

Препринт не прошёл рецензирование; он используется как открытый обзор и не
заменяет первичные публикации Haworth и Pixler.
