# Normalized gas and LBA correlation

## Explicit mapping of saved lithology

For developers: review_lithology_source reads a selected interval_id on a verified metre MD axis. create_lithology_mapping requires explicit mapping_id, reviewer, applicability_reference, RockFamily and quality; evaluate_lithology_mapping rechecks the source before emitting LithologyObservation. Interval, description, catalog or axis changes invalidate prior review. Names never select a family automatically. This is a session-local data-only API without UI or persistence; a geologist supplies applicability confirmation and regional reference data.

## Purpose

The Interpretation Reports workspace keeps ready normalized gas received from a server or file separate from normalized gas calculated by the program. Local calculation never overwrites the server data.

## Where the commands are

The calculation is available from two places and uses one controller and one shared input plan:

- **Calculations → Normalized gas and DEXP…** — the primary engineering dialog;
- the normalized-gas card in **Interpretation reports** — the same calculation mechanism followed by interval analysis and report generation.

The report card also keeps the server/local/compare mode selector, detected-curve statuses, the tablet-track command, and report refresh with charts.

## Shared drilling-input dialog

The dialog has three tabs:

1. **Drilling inputs** — ROP, FLOW, RPM, WOB, and actual mud density. Each parameter may use automatic selection, a specific curve, or a manual constant.
2. **BIT sections** — actual hole size from BIT/BS/HOLE_SIZE, one constant, or an MD interval table.
3. **Reference and DEXPC** — `ROP_REF`, `BIT_REF`, `FLOW_REF`, gas-system efficiency, and normal mud density.

`BIT_REF` is only the normalization reference. It never replaces the actual bit diameter.

### Multiple hole sections

When hole size changes, use a section table:

```text
MD top | MD bottom | diameter | unit | comment
0      | 420       | 311.2    | mm   | conductor section
420    | 1680      | 215.9    | mm   | intermediate section
1680   | 2500      | 155.6    | mm   | production section
```

The program builds the actual depth-indexed `BIT` value from the matching row. Overlaps, uncovered depths, non-positive values, and unsupported units block calculation. One constant is valid only when the complete calculation range was drilled with one diameter.

### Duplicate technology channels

Automatic selection merges two channels only when units, sample count, missing-value positions, and numeric values agree. For example, identical `S106` and `S106_TEHNOLOGIYA` are treated as one source. If values differ, the ambiguity remains and the user must select a curve explicitly.

## Report modes

The **Report mode** field provides three options:

1. **Server + local calculation — compare both**. The ready server/file curve remains unchanged, the program calculates a separate `TG_NORM_CALC` curve, and the report analyses both series.
2. **Server/file curve only**. Only the supplier's ready curve is used to detect gas anomalies. Local `TG_NORM_CALC` is not recalculated.
3. **Local program calculation only**. The report uses `TG_NORM_CALC`; the ready server curve remains in the dataset but is excluded from the current analysis.

## Server curves

A source curve whose provenance does not start with `calculation:` is treated as a server or file source. The principal supported mnemonics are:

- `TG_NORM`;
- `NORMALIZED_TOTAL_GAS`;
- `TOTAL_GAS_NORM`;
- `NORM_TG`;
- `TGNORM`.

The original mnemonic, unit, and values are retained. Before engineering use, verify the supplier's formula, units, and normalization settings.

## Local normalized-gas calculation

The local total is always stored separately as `TG_NORM_CALC`. The calculation requires:

- C1, C2, C3, and the available C4/C5 components;
- actual depth-indexed ROP;
- actual depth-indexed BIT/BS diameter;
- actual FLOW_IN or FLOW_OUT;
- reference `ROP_REF`, `BIT_REF`, and `FLOW_REF`;
- gas-system efficiency `E`.

Compatible actual-curve units are converted to ft/h, in, and gpm. The total-series formula is:

```text
TG_NORM_CALC = SUM(C1..NC5)
               × (ROP_REF / ROP)
               × (BIT_REF / BIT)²
               × (FLOW / FLOW_REF)
               / E
```

The formula is implemented by profile `gas.normalized_total_reference_us20150060054`; the result provenance records the profile version and the reference parameters used.

## DEXP and DEXPC

DEXP requires depth-aligned `ROP`, `RPM`, `WOB`, and actual `BIT`. The same BIT section table is used by normalized gas and DEXP. DEXPC additionally requires calculated DEXP, actual mud density, and a specified normal mud density. Failure of one method does not remove the other available results or tracks.

## Interval correlation

Every selected gas series is analysed independently:

1. the program builds a `log1p` representation of valid values;
2. a median baseline and robust scale are estimated separately for that series;
3. continuous prospective intervals are detected at the selected robust-z threshold;
4. Haworth/Pixler context and a preliminary fluid hypothesis are calculated for every interval;
5. every overlapping LBA sample is assessed under the LBA standard;
6. the gas hypothesis and LBA evidence are classified as concordant, partly concordant, divergent, mixed, or insufficient.

In comparison mode, the server and local series are not arithmetically merged or forced onto an artificial common scale. Each uses its own robust baseline. The report retains the source of every prospective interval and states the number of matching, server-only, and local-only intervals.

Server total normalized gas is not compared with local `C1_NORM`, because they are different measurements. Comparing the two sources requires local total `TG_NORM_CALC` or a compatible calculated legacy `TG_NORM`.

## Limitations

- A prospective interval is not a final geological conclusion.
- Do not compare absolute values between the two series until their units and normalization methods have been verified.
- Account for gas lag, degasser operation, ROP/FLOW/BIT changes, lithology, and LBA quality.
- At least 20 valid samples are required for a stable baseline in each analysed series.
- Recalculate after changing BIT sections, selected channels, or reference parameters.

## Formula source

The local formula passport cites US20150060054A1 and is stored with a control example in the project formula registry.


## Preliminary GIS + mud gas + LBA + lithology review (INTERP-FUSION-01)

**Current implementation:** a testable **data-only** method in
`services/gis_gti_lithology_screening.py`. It is **not connected**
to raw LAS ingestion, the production UI or reports. Existing
Haworth/Pixler/OPUS and LBA interpretation remain separate.
This is a contract for later integration, not an available menu action.

For a single verified MD axis (metres and a matching axis ID),
the method accepts independently validated observations: effective
porosity, fractures, NMR mobility, tight matrix, calibrated high/low
water saturation `Sw`, GIS gas effect, mud gas, LBA and actual
gas/oil/water formation-test results. Each observation requires its
source ID, depth interval and QC; a derived GIS observation also
requires a method/calibration reference. This does **not** interpret
raw `GR`, `RT`, `RHOB`, `NPHI` curves: semantic resolution,
quality control and numerical models are separate INTERP-GIS/PETRO work.

### Lithology and exceptions

- **Clastics/carbonates:** evaluate porosity, resistivity and
  saturation with matrix composition, Rw, invasion and borehole QC.
- **Argillite/clay/coaly rocks:** a mud-gas show or LBA does **not**
  turn tight rock into a proven reservoir; investigate fractures,
  secondary storage, thin interbeds and unconventional reservoirs.
- **Salt, gypsum, anhydrite:** high resistivity alone **does not**
  identify oil; review contacts, inclusions, fractures and formation tests.
- **Tuff/volcanic rocks:** do not apply uncalibrated clastic/carbonate
  parameters; secondary porosity or fractures can make real reservoirs.

Actual fluid sampling has more diagnostic authority than an LBA or gas
hypothesis; however, tests grouped into one broad interval may represent
different beds. Multiple tested phases therefore trigger a conflict
review, not an automatic claim of uniform gas and water. `Sw`
does not distinguish oil from gas; high `Rt` in tight rock does not
prove hydrocarbons. Suspect curves are excluded and uncovered depths
remain unknown. A shortlist flag means **geologist review**, not
commercial pay or proven recoverable reserves.

Later GIS processing must recognize tools, units and vendor mnemonics
via Energistics PWLS, including gamma/spectral gamma/SP, RHOB/NPHI/DT/CALI,
deep/shallow RT, NMR, image logs, pressure and fluid sampling.
Well/facies-specific calibration, separate log passes, MD/TVD, mud-gas
lag and measurement QC must be checked independently. Do not impose
universal lithology cutoffs.

Sources:
[SLB Basic Well Log Interpretation](https://www.slb.com/resource-library/oilfield-review/defining-series/defining-log-interpretation),
[SLB Measuring Porosity](https://www.slb.com/resource-library/oilfield-review/defining-series/defining-porosity),
[AAPG Reservoir](https://wiki.aapg.org/Reservoir),
[Energistics PWLS](https://energistics.org/practical-well-log-standard).

## Comparing the LBA residual-ring score with mud gas

Record the bitumoid group/type, fluorescence colour and the **1–5
UV-fluorescent capillary-extract spot score** separately.
**Score 2 means a thin, broken UV-fluorescent ring**; the observed fluorescence is also relevant.
The historical LAS field name `lba_intensity` does not change that meaning;
the UV-fluorescent imprint is distinct from a solvent-cut residue observation.

Correlation with gas anomalies, Haworth and Pixler requires verified
sample depth and gas lag. The LBA group or ring score cannot calculate
oil/water saturation or prove commercial productivity.

### Operator LBA patterns: field hypotheses, not fluid identification

`lba_operator_screening.py` contains **selected field observations
provided by an experienced mud logger**. They are not international
cutoffs and have not been calibrated as a general reservoir model.

| LBA | Possible context before independent gas/GIS correlation |
|---|---|
| `1-БГ-ЛБ` | Trace light bitumoid. Sometimes accompanies gas shows, but organic material or drilling additives may explain it. |
| `2-БГ-ЛБ` | Gas/gas-condensate context, occasionally light oil; no established fluid phase. |
| `2-БЖ-МБ`, `3-БЖ-МБ`, `3-ГЖ-МБ` | Light oil or condensate/gas-condensate is possible; review C2–C5, solvent cut, gas background and GIS. |
| `3-ОЖ-МСБ` | Oily-resinous show; could be formation oil or residual organic bitumen, not proven movable oil. |

**Mandatory QC:** sample lag and provenance, a control extract from
mud/solvent, coal and coaly layers, natural organic material, and
timing of lubricating/organic mud additives (the operator mentioned
“Петролюб” and “Суперборетрол”; their chemical composition is not assumed).
When contamination is suspected, the helper suppresses phase hypotheses.
Missing checks or unlisted patterns remain uncertain. Methane alone
cannot explain the fluorescence of an extracted bitumoid; examine
co-occurring extractable organics.

This feature is **data-only API**, not yet connected to the report,
Haworth/Pixler/OPUS or the UI. Coupled gas/GIS interpretation requires
a separately verified integration. The 1–5 score is **not** pore-fluid
hydrocarbon saturation.

## GIS input inventory — a separate INTERP-GIS-01 stage

`inventory_gis_inputs` is currently a data-only API without a UI command.
It checks saved semantics/UOM and a metre MD axis; TVD/ft/unverified lag and
unknown units remain explicit limitations. Counts and bounds of finite
depth/value pairs do not establish continuous coverage.
Source LAS bytes and arrays remain unchanged. This is not calibration,
a Vsh/Sw calculation, fluid identification or confirmation of tool applicability.

## Actual GIS/GTI MD cells

`review_gis_gti_intervals` is a separate data-only MD-cell review in
INTERP-FUSION-01. For one explicitly stated rock family, the window is split
at validated interpretation-observation boundaries; it does not read raw LAS.
Existing `review_gis_gti_interval` screening applies per cell; uncovered cells
remain unknown. Touching is not overlap: separated GIS/GTI indicators do not
form a joint candidate, and different tests conflict only on their actual
intersection. Source IDs and suspect/rejected QC are retained. Verified MD/lag
and method applicability are prerequisites. No UI, automatic cell merging,
productive-bed count/thickness or new fluid model is added; changing rock
families require separate verified windows.

## Lithology on the common MD evidence partition

`review_gis_gti_lithology_intervals` is a separate data-only API for explicit
`LithologyObservation` records: source ID, MD-axis ID, bounds, RockFamily and
ObservationQuality. Evidence and lithology share a common boundary partition.
Only an agreed VALIDATED family is used per cell; missing or competing families
give UNKNOWN_OR_MIXED with separate QC reasons. Suspect/rejected records do
not select a rock family, but their IDs are retained. Recorded UNKNOWN differs
from missing lithology. Independent formation tests retain their authority;
a positive shortlist does not resolve lithology QC or approve a geologist's
conclusion. Raw rock-name mapping, MD/lag, UI and persistence remain separate;
source LAS and project data are unchanged.

## Comparison freshness during Excel export

A changed source curve revision or replaced curve/axis array requires a new
standard/OPUS comparison. Stale comparisons are omitted from a new export;
if the source changes after XLSX generation starts, export stops before
replacing an existing file. Source LAS data remains unchanged.
