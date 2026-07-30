# Mud-gas interpretation and whole-well report

## What the workspace does

The **Interpretation reports** tab works with the active well and the complete current
depth dataset. It can:

1. calculate the standard Gas Ratio, Haworth, Pixler, drilling-normalized methane,
   `DEXP`, and optional `DEXPC` suite;
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
3. Enter normal mud density in ppg only when `DEXPC` is required. Zero means “not set”;
   no regional default is silently injected.
4. Select **Calculate standard methods**.
5. Review the new tablet curves, gas lag, units, and source-channel quality.
6. Refresh the analysis and inspect the candidate intervals.
7. Confirm accepted intervals through **Edit → Interpretation intervals…**, including a
   type, label, and comment.
8. Refresh and export XLSX, DOCX, or PDF.
9. Save the project with **Ctrl+S**.

A repeated calculation updates only curves whose provenance starts with `calculation:`.
An existing source curve with the same mnemonic is protected and reported as an issue.

## Calculated curves

| Group | Outputs |
|---|---|
| Basic ratios | `C2_C3`, `C1_C2C3`, `TG_CALC`, component-relative percentages |
| Haworth | `WH`, `BH`, `CH` |
| Pixler | `C1_C2`, `C1_C3`, `C1_C4`, `C1_C5` |
| Normalized gas | `C1_NORM` |
| Drilling context | `DEXP`, optional `DEXPC`; existing `NCT` and `DEXPC_NCT` are shown with them |

Total C4/C5 channels and split `iC4/nC4`, `iC5/nC5` channels are both supported.
A total channel is used as the sum without inventing an isomer split. Percent, ppm,
ppb, and fractional gas concentrations are converted to a compatible scale.

ROP, bit size, flow, WOB, and mud density are converted to the explicit formula-profile
units. WOB reported in kg or tonnes is converted to force only in the semantic WOB
context using standard gravity. An unknown or ambiguous unit blocks that calculation.

## Candidate detection

The primary gas curve is selected in this order:
`C1_NORM` → `TG_NORM` → `TG_CALC` → source Total Gas.

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

Each candidate also receives a **preliminary fluid interpretation**. The
C2–C5 fraction inside the interval is compared with the robust background of the
current well:

- relative depletion in heavier components — “probable gas”;
- relative enrichment — “probable liquid hydrocarbons (oil/condensate)”;
- weak separation — “mixed/indeterminate hydrocarbon show”;
- insufficient C1–C5 — “gas hydrocarbon show; component data are insufficient.”

This is a relative fluid facies, not a universal palette. The application does
not infer water from absent mud gas; that requires logs, petrophysics, and/or
formation testing. A C2–C5 fraction difference is treated as material at
`|robust z| ≥ 2.0`; this is a statistical background-comparison threshold, not
a fluid-type boundary.

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
- **PDF/print**: the current preview rendered for distribution.

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

Historical palettes and thresholds from legacy working spreadsheets remain reference
material only. They require local calibration against the region, instrumentation,
gas extractor, and confirmed well results.
