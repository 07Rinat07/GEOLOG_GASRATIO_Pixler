# Archie: independent field-acceptance protocol

## Status and applicability limits

**Development-stage status: FIELD ACCEPTANCE NOT PERFORMED.** Software gates, synthetic regression tests and the transient Sw tablet preview establish software behavior only. They do not establish that any particular well meets Archie assumptions, that φ is effective porosity, Rt is true formation resistivity, or Rw has been established at formation temperature.

Use only traceable records and model versions for the actual well. Do not populate missing inputs with assumed or typical values. Sw by itself cannot identify oil, gas or commercial productivity.

## Register of mandatory evidence

| Review subject | Record for review | Reject or leave unverified when |
|---|---|---|
| Source identity | Well, MD interval, dataset/run IDs, original LAS/logs, versions and depth reference | Original records cannot be traced or runs/depths do not match |
| Depth axis | MD in metres, sample order, measured gaps and independently reviewed φ/Rt alignment | Unjustified depth match, implicit cross-run join or interpolation without a separate method |
| Effective porosity φ | Determination method, v/v unit, corrections, core/independent comparison if available, uncertainty | Raw NPHI or total porosity is treated as proven effective φ |
| True Rt | Tool, depth of investigation, invasion and borehole effects, corrections and ohm.m units | An arbitrary resistivity curve is accepted as true Rt without supporting interpretation |
| Formation water Rw | Sample or independent source, available salinity/composition, temperature, correction to formation temperature and uncertainty | Rw source, temperature or unit scale is unknown |
| Coefficients a, m, n | Basis of each value, core/special studies when available, assessed Sw sensitivity | Coefficients are auto-filled or selected without evidence |
| Archie applicability | Rock character, conductive constituents, shale, fractures and other conductivity pathways | Material alternative conduction is not addressed or assumptions are untested |
| Independent comparison | Available core saturations, laboratory work, formation tests, other interpretations, interval and discrepancy | Material disagreement is unexplained or evidence required for the requested approval level is missing |

Missing evidence means **unverified**, not zero and not approved. Particular additional tests may be unavailable; record that fact as an explicit confidence limitation. The responsible interpreter defines an appropriate acceptance level under an approved local interpretation program.

## Interval-level review

1. Check exact source MD rows, observed gaps and QC; do not fill, smooth or silently join mismatched depths.
2. Record the actual Rw, a, m, n and φ/Rt versions; ensure percent and kOhm-m are not silently reinterpreted.
3. Independently recalculate Sw for selected measured depths using the documented Archie equation and original inputs.
4. Flag missing/invalid measurements and Sw outside its physical range; **do not clip Sw to 0–1** to hide inconsistencies.
5. Examine sensitivity to φ, Rt, Rw, a, m, n uncertainty and reservoir heterogeneity; obtain numerical tolerances from evidence rather than inventing universal thresholds.
6. If a production or fluid claim is required, check it against **independent** well tests and formation information. Archie alone establishes neither fluid phase nor flow rate.

## Decision and responsibility

Record well and interval, exact source versions, parameter basis, discrepancies, retained limitations, independent reviewer and date. Permitted conclusions are **“not reviewed”**, **“additional data or correction required”**, and **“reviewed with enumerated limitations”**. Only the responsible petrophysicist may issue the latter after evaluating the required evidence and locally approved quality criteria. A successful CI result must never automatically set field status to approved.

Reassess the decision whenever source curves, depth axis, formation conditions or model coefficients change.

## Software verification is not field acceptance

The current application provides read-only calculations and visualization from provenance-checked native GIS data: φ/Rt are explicit, units are checked, missing samples and QC are preserved, and LAS remains unchanged. This is **technical readiness for expert review**, not a certification of physical accuracy on a real well.

Related guide: [petrophysical reference models](PETROPHYSICAL_REFERENCE_MODELS.md).
