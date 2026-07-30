# Normalized gas and LBA correlation

## Purpose

The Interpretation Reports workspace keeps ready normalized gas received from a server or file separate from normalized gas calculated by the program. Local calculation never overwrites the server data.

## Modes

The **Normalized-gas mode** field provides three options:

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

## Local calculation

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

## Interval correlation

Every selected gas series is analysed independently:

1. the program builds a `log1p` representation of valid values;
2. a median baseline and robust scale are estimated separately for that series;
3. continuous candidate intervals are detected at the selected robust-z threshold;
4. Haworth/Pixler context and a preliminary fluid hypothesis are calculated for every interval;
5. every overlapping LBA sample is assessed under the LBA standard;
6. the gas hypothesis and LBA evidence are classified as concordant, partly concordant, divergent, mixed, or insufficient.

In comparison mode, the server and local series are not arithmetically merged or forced onto an artificial common scale. Each uses its own robust baseline. The report retains the source of every candidate and states the number of matching, server-only, and local-only intervals.

## Limitations

- A candidate interval is not a final geological conclusion.
- Do not compare absolute values between the two series until their units and normalization methods have been verified.
- Account for gas lag, degasser operation, ROP/FLOW/BIT changes, lithology, and LBA quality.
- At least 20 valid samples are required for a stable baseline in each analysed series.
- Recalculate the local curve after changing reference parameters.

## Formula source

The local formula passport cites US20150060054A1 and is stored with a control example in the project formula registry.
