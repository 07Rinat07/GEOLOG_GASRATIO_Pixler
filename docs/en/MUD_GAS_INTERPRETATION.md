# Mud-gas interpretation and whole-well report

## What the workspace does

The **Interpretation reports** tab works with the active well and the complete current
depth dataset. It can:

1. calculate the standard Gas Ratio, Haworth, Pixler, normalized C1–C5 and
   `TG_NORM`, `DEXP`, and optional `DEXPC` suite;
2. add the calculated curves to the dataset and display separate
   **Gas Ratio / Pixler**, **Normalized gas**, and **DEXP / NCT** tracks;
3. scan the whole well for relative gas-anomaly intervals;
4. keep automatic candidates separate from geologist-confirmed intervals;
5. export XLSX, DOCX, PDF, or print through the system dialog.

The source LAS is never overwritten. Calculated curves, manual intervals, and the
layout are persisted in the `*.geolog.json` project with **Ctrl+S**. Report files are
separate outputs and do not save the project.

## Workflow

1. Open LAS/GS2 and review the C1–C5, ROP, RPM, WOB, BIT, FLOW, and mud-density mappings.
2. Open **Interpretation reports**.
3. Review the visible ROP/BIT/FLOW/E gas-normalization references. The initial
   50 ft/h, 10 in, 500 gpm, and 1.0 values are editable conditions, not measurements.
4. Enter normal mud density in ppg only when `DEXPC` is required. Zero means “not set”;
   no regional default is silently injected.
5. Select **Calculate standard methods**.
6. Review the new tablet curves, gas lag, units, and source-channel quality.
7. Refresh the analysis and inspect the candidate intervals.
8. Confirm accepted intervals through **Edit → Interpretation intervals…**, including a
   type, label, and comment.
9. Refresh and export XLSX, DOCX, or PDF.
10. Save the project with **Ctrl+S**.

A repeated calculation updates only curves whose provenance starts with `calculation:`.
An existing source curve with the same mnemonic is protected and reported as an issue.

## Calculated curves

| Group | Outputs |
|---|---|
| Basic ratios | `C2_C3`, `C1_C2C3`, `TG_CALC`, component-relative percentages |
| Haworth | `WH`, `BH`, `CH` |
| Pixler | `C1_C2`, `C1_C3`, `C1_C4`, `C1_C5` |
| Normalized gas | `C1_NORM`, `C1_NORM_REF`, `C2_NORM`, `C3_NORM`, available i/n-C4/C5_NORM, and `TG_NORM` |
| Drilling context | `DEXP`, optional `DEXPC`; existing `NCT` and `DEXPC_NCT` are shown with them |

Total C4/C5 channels and split `iC4/nC4`, `iC5/nC5` channels are both supported.
A total channel is used as the sum without inventing an isomer split. Percent, ppm,
ppb, and fractional gas concentrations are converted to a compatible scale.

ROP, bit size, flow, WOB, and mud density are converted to the explicit formula-profile
units. WOB reported in kg or tonnes is converted to force only in the semantic WOB
context using standard gravity. An unknown or ambiguous unit blocks that calculation.

## Candidate detection

The primary gas curve is selected in this order:
`TG_NORM` → `C1_NORM_REF` → `C1_NORM` → `TG_CALC` → source Total Gas.

With at least 20 valid samples, the detector:

- applies `log1p` to limit the leverage of isolated large peaks;
- estimates a robust whole-well baseline with median and MAD, falling back to IQR
  or standard deviation when necessary;
- flags points above the selected robust-z threshold;
- joins adjacent points using the median depth step;
- attaches available Haworth/Pixler/DEXP interval medians as context.

The default `3.0` threshold is a starting point, not a universal geological cutoff.
`low/medium/high` describes only relative anomaly strength and continuity; it is not
a probability of hydrocarbon saturation.

Each candidate also receives a **preliminary fluid interpretation**. Components are
integrated over the interval, so sparse non-zero C2–C5 values are not hidden by a
pointwise median. Interval, background, and robust z are printed with five decimal
places; the count column is named **Points above threshold**.

The primary palette uses:

```text
Wh = 100 × (C2 + C3 + iC4 + nC4 + iC5 + nC5) /
           (C1 + C2 + C3 + iC4 + nC4 + iC5 + nC5)
Bh = (C1 + C2) / (C3 + iC4 + nC4 + iC5 + nC5)
Ch = (iC4 + nC4 + iC5 + nC5) / C3
```

`Bh > 100` and `Wh < 0.5` identify very light/dry-gas screening regions;
`Wh = 0.5–17.5` is the gas-to-condensate/light-oil transition; `Wh = 17.5–40`
is the oil region; and `Wh > 40` is heavy/residual oil. Bh supplies the light/heavy
balance. Ch confirms the transition: `Ch < 0.5` supports a productive gas phase,
whereas `Ch > 0.5` supports an associated liquid phase or light oil. The opposite
unattributed Ch scale found in working notes is deliberately not mixed into this profile.

Pixler uses interval-integrated `C1/C2`, `C1/C3`, `C1/C4`, and `C1/C5`.
Overlapping C1/C2 bands are reported explicitly. A fall from C1/C3 to C1/C4 is only
flagged as **possible formation-water influence**; it is not an automatic “water”
classification. Productivity and permeability require locally calibrated boundary lines.

## Gas/LBA correlation

Every gas anomaly is matched to depth-overlapping cuttings samples. The LBA reference
keeps two independent scales:

- groups 1–5 describe fluorescence colour, composition, and bitumoid type
  (`LB`, `MB`, `MSB`, `SB`, `SAB`);
- intensity 1–5 describes the fluorescence pattern, from isolated points to a solid spot.

The report keeps Wh/Bh/Ch, Pixler, source LBA observations, the standard LBA assessment,
the geologist’s conclusion, and the correlation result separate. Correlation is reported
as **concordant / partly concordant / divergent / mixed evidence**. Groups 1–3 generally
support a light or transitional hydrocarbon phase, whereas groups 4–5 support a
resinous/heavier liquid phase. Intensity strengthens an observation but does not set
the fluid type by itself, and conflicting observations are never overwritten.

## Gas mixture ramp report

The **Report type** selector provides two modes for a delivered sample:

- **Gas mixture ramp — time chart**: raw C1–C5 detector response versus time,
  composition table, Wh/Bh/Ch, Pixler ratios, and a preliminary result;
- **Gas mixture ramp — interpretation only**: the same calculations and result
  without the chart for compact printing.

The input must be a time dataset with consistent C1, C2, C3, C4, and C5 curves;
split i/n-C4 and i/n-C5 are summed automatically. A component baseline is estimated
from the lower part of its time response. Composition uses the median baseline-corrected
values where total response is at least 50% of its peak. A constant signal with no rise
above baseline is reported as **background response or insufficient hydrocarbons**.

The screening result uses the same Wh/Bh/Ch palette as the interval report: dry gas,
gas with increasing heavy hydrocarbons, wet gas/gas condensate, light oil, oil, or
heavy/residual oil. The working Wh bands are `<0.5%`, `0.5–17.5%`, `17.5–40%`,
and `>40%`; Bh and Ch refine the transition regions. The report always labels this
as preliminary interpretation, not a
quantitative chromatographic certificate. Mole fractions require calibration,
reference gas, zero checks, and uncertainty assessment under ISO 6974-1. Water is
not inferred from C1–C5.

## Interpretation boundary

The automatic output is a **candidate hydrocarbon-show interval**, and fluid
character is stated as a preliminary interpretation. It does not establish
commercial reservoir quality, a definitive fluid type, permeability, saturation,
pore pressure, or a mud-weight recommendation.

Before confirmation, correlate Total Gas and C1–C5, Haworth/Pixler, lithology, cuttings,
LBA/fluorescence, calcimetry, ROP and drilling conditions, gas lag, extractor and
chromatograph stability, wireline/LWD logs, and test results. `DEXP/DEXPC` is drilling
and pressure context, not direct hydrocarbon evidence.

## Report contents

- **XLSX**: summary, candidate intervals, manual intervals, methods/sources, and a
  whole-well data sheet. Text is neutralized against spreadsheet formula injection.
- **DOCX**: editable methods, candidates, manual confirmations, and limitations.
- **PDF/print**: the current preview rendered for distribution; a ramp report can
  include its time chart or use the separate compact interpretation-only mode.

## References

1. Haworth J. H., Sellens M., Whittaker A. (1985). *Interpretation of Hydrocarbon
   Shows Using Light (C1–C5) Hydrocarbon Gases from Mud-Log Data*. AAPG Bulletin
   69(8), 1305–1310.
2. Pixler B. O. (1969). *Formation Evaluation by Analysis of Hydrocarbon Ratios*.
   Journal of Petroleum Technology 21(6), 665–670. DOI `10.2118/2254-PA`.
3. Jorden J. R., Shirley O. J. (1966). *Application of Drilling Performance Data
   to Overpressure Detection*. DOI `10.2118/1407-PA`.
4. Rehm W. A., McClendon R. (1971). *Measurement of Formation Pressure from
   Drilling Data*. DOI `10.2118/3601-MS`.
5. Lukyanov E. E., Strelchenko V. V. (1997). *Geological and technological
   investigations while drilling*. Moscow: Neft i Gaz. ISBN `5-7246-0042-0`.
6. Normalization profiles: US20140379265A1/EP2772775A1 and US20150060054A1.
7. SLB (2012). *Mud Logging: Looking Beyond the Formation*. Oilfield Review:
   C1–C5, balance/wetness, and additional components are used for preliminary
   fluid-facies characterization.
8. Hawker D. P. (1997). *Hydrocarbon Evaluation and Interpretation*. DATALOG
   Training Department. Source for the working GWR/Wh, LHR/Bh, and OCQ/Ch palette.
9. Trubetskoy K. N., Kaplunov D. R. (eds.) (2016). *Mining: Terminological
   Dictionary*. Moscow: Gornaya Kniga, pp. 91–92. ISBN `978-5-04-119548-9`.
10. Krasnoshchekov V. V. (1971). “Gas analysis.” *Great Soviet Encyclopedia*,
    vol. 6, pp. 15–16.
11. The supplied legacy translations *Gas-factor analysis* and *Pixler
    interpretation* are working explanatory material. Detected formula/range
    typographical errors are not copied into the calculation core.

Historical palettes and thresholds from legacy working spreadsheets remain reference
material only. They require local calibration against the region, instrumentation,
gas extractor, and confirmed well results.
