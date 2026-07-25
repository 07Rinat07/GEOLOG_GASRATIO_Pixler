# GEOLOG GASRATIO@Pixler project plan

Current as of 25 July 2026. Version **0.7.67** uses project format **v20**,
form schema **v8**, and tablet layout **v18**.

## Completed

- [x] remove the duplicated generic **Scale** caption from every numeric curve header;
- [x] label the ruler with the parameter name and unit, for example **Weight on bit · t**;
- [x] reduce a complete block from 58 to 44 px without losing range editing or `A`/`⚙` actions;
- [x] apply the change to all factory, ready, and user forms through the shared renderer;
- [x] preserve complete-row scrolling and project v20 / form v8 / tablet v18 compatibility;
- [x] update RU/KK/EN documentation and regression tests.

## Next stage

- [ ] visually verify headers on Windows at track widths of 80, 120, 160, and 250 px;
- [ ] confirm long localized names remain readable and elide correctly;
- [ ] continue the approved project plan after user acceptance.

## Acceptance criterion

Instead of a generic **Scale** caption, every ruler shows its own parameter name. Editable minimum,
unit, maximum, `A`, `⚙`, endpoints, and ticks remain available. No factory, ready, or user form
requires manual updating.
