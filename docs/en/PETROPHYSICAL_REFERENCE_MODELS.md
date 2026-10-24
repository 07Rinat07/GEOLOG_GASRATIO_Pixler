# Petrophysical reference calculations: IGR, porosity and Archie

## Saved source details

The Depth axis tab is available without curve selection and with an empty
curve catalog. It shows dataset/axis IDs, the original unit, saved alignment
evidence and QC. Missing evidence is explicit; recorded evidence does not
certify correct alignment or geological approval. Clearing curve selection
does not clear this tab. Axis details and QC share the opening snapshot;
reopen the window to refresh them.

Select one curve in the GIS inventory to inspect its dataset, axis and curve IDs,
curve key, original and saved canonical mnemonic, saved family, source ID,
provenance, version and recognition evidence. Missing records are marked
explicitly. Values are literal source text; they do not certify calibration or
geological approval. Details and QC share the snapshot taken when the window
opened. Reopen to inspect subsequent source changes. Clearing selection clears
all details. The two tables can be resized with the divider; neither edits data.

## Purpose and availability

This guide describes isolated calculation code in PR #686 (INTERP-PETRO-01), **not a UI command**. The reference functions were integrated through PR #686; the operator dialog is described below. `geoworkbench.services.petrophysical_reference_models` accepts previously verified scalar inputs and returns an immutable result with `method_id`, `value`, `unit`, `quality`, and `parameters`. It does not discover LAS mnemonics, convert units, align MD/TVD, or modify the project.

## Explicit source input review

`review_gis_reference_input(dataset, method_id=..., curve_key=...)` is a separate
data-only API before calibration. `igr-linear-1` requires gamma_ray/API;
`density-porosity-1` requires bulk_density/g/cm3. A fresh inventory checks metre
MD, semantics, provenance, current state and actual paired samples. Equivalent
unit spellings are accepted; other scales (kg/m3 or uR/h) are rejected without
conversion. No channel is selected automatically. `ready_for_calibration`
does not establish tool/model applicability or calibration and does not authorize
a future calculation using a stale review. Archie is excluded: generic
resistivity/neutron does not establish Rt/effective porosity. UI, source LAS,
arrays and project persistence are unchanged.

`create_gis_reference_calibration` requires calibration_id, tool_id, reviewer,
applicability_reference (expert review evidence), MD bounds and all method
parameters. `evaluate_gis_reference_sample` evaluates one actual sample_index
with source MD/value and full calibration context. There are no default
parameters, interpolation or clipping. Curve revision/metadata, replaced
arrays, in-place MD edits or reopen require a new profile. Profiles are
session-local and are not saved. Evidence records an expert attestation, not
automatic tool applicability certification. NaN, invalid indices and samples
outside the MD scope are rejected. Controllers must increment curve.version
for in-place value edits. This is not a batch-loop API: every sample rechecks
inventory and MD. Archie is not connected.

**Operator dialog:** Calculations → GIS: review one sample…
(`GisReferenceDialog`, `petro_reference.action`). Select the active GIS dataset,
method and curve; enter calibration/tool IDs, reviewer, evidence, MD bounds
and parameters. Choose the source row (from 1), then click Evaluate sample.
Use a decimal dot or comma without thousands separators. The dialog displays
source MD/value/unit, result, QC and calibration ID. Editing a field clears the
result; changing the method clears parameters. Close leaves the project unchanged.
There is no profile saving, derived curve, export or fluid identification.
Invalid fields, NaN, stale sources and incompatible units block calculation.
Synthetic numerical checks do not replace tool/regional field acceptance.

**GIS source inventory:** click Source GIS inventory in the same dialog.
The separate table shows source IDs, units, finite paired MD/value sample
counts, **actual measured** MD bounds and QC issues. The axis header shows
the original direction, including bottom-up decreasing MD. Duplicate and
non-monotonic axes are flagged rather than sorted; NULLs are not
interpolated. Each opening rechecks the current source without changing
LAS, the project or entered calibration. This does not certify continuous
coverage, calibration, saturation or productivity.

## Gamma ray: IGR

`gamma_ray_index` (`igr-linear-1`): `IGR = (GR - GRclean) / (GRshale - GRclean)`. All three inputs must use the same verified API scale; `GRshale > GRclean`. **Synthetic**, not field, reference example: `GR=65`, `GRclean=25`, `GRshale=125` API → `IGR=0.4` v/v. IGR is **not automatically Vsh**: mineralogy, facies and local reference endpoints need verification. Values outside [0,1] are retained with `outside_reference_range` rather than clipped.

## Density porosity

`density_porosity` (`density-porosity-1`): `phiD = (rho_matrix - rho_bulk) / (rho_matrix - rho_fluid)`. Densities must be explicitly supplied in g/cm³, with `rho_matrix > rho_fluid > 0`. Synthetic example: `rho_bulk=2.42`, `rho_matrix=2.71`, `rho_fluid=1.0` → `phiD≈0.16959` v/v. Negative or greater-than-one results are retained with `outside_physical_range`, not replaced with zero. Matrix density must not be guessed without rock evidence.

## Archie water saturation

`archie_water_saturation` (`archie-water-saturation-1`): `Sw = (a * Rw / (phi**m * Rt))**(1/n)`. Explicit `phi` (0 < φ ≤ 1), `Rt` and `Rw` (ohm·m), `a`, `m`, `n` (>0) are required. Synthetic example: `phi=0.2`, `Rt=10`, `Rw=0.1`, `a=1`, `m=2`, `n=2` → `Sw=0.5` v/v. Apply the equation only after checking reservoir type, water, temperature and coefficients. `Sw>1` is retained as `outside_physical_range` and does not establish fluid type.

## Quality control and next steps

`valid` means only that the numerical result is admissible for the **supplied** inputs; it does not certify calibration or producibility. Non-finite, zero and inconsistent inputs raise `ValueError`; there are no implicit coefficients, oil/gas cutoffs or LAS value translations. Next steps are GIS source provenance, unit and depth-axis validation, operator UI integration, and independent petrophysical/field acceptance. Original sample values and LAS mnemonics remain unchanged. See the [plan](../PROJECT_PLAN.md) and [requirements](../REQUIREMENTS.md).

Before entering calibration, use **Review selected source** after selecting a method and curve. The review explains axis, channel identity/state, family and unit-scale blockers. Passing source checks is not calibration or interpretation approval. Repeat the review after source changes; method/channel changes clear it, and evaluation rechecks the live source. Entered evidence is preserved.

Select the source row beside the method and curve, then review the source to see its actual MD, value and original unit before calibration. The preview uses exactly that row, including descending acquisition order. Missing/non-finite or removed samples are unavailable; no neighboring value is substituted. Changing the selection clears the preview; repeat review to read current data.
