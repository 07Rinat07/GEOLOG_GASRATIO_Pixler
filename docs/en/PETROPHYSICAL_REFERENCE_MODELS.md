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
arrays, in-place MD edits or reopen require a new profile. Active calibrations are
session-local and are not saved; separate parameter records are described below.
Evidence records an expert attestation, not
automatic tool applicability certification. NaN, invalid indices and samples
outside the MD scope are rejected. Controllers must increment curve.version
for in-place value edits. The scalar API is not a batch-loop API: each call rechecks
inventory and MD. Use `evaluate_gis_reference_profile` for an interval (see below).
Archie is not connected.

“Review samples in interval” counts actual values and missing samples of the
selected curve between the entered MD bounds. When measured values are available,
the summary shows their shallowest and deepest depths at stored MD precision.
A single observation has equal bounds. Up to ten missing sample depths are shown
at their stored MD precision in source row order. This is a snapshot.
Review again after source changes. Point counts do not establish continuous
coverage, correlation, or fluid type.

For GR, RHOB, NPHI, DT, resistivity and other recognized GIS channels, select a
curve and choose “Review original GIS samples” without selecting a method. Source
unit, semantics, axis and provenance are checked; no unit conversion, calibration
or petrophysical calculation is performed. A fully missing curve is reported as
missing samples, not as a negative result or a statement about the whole well.
“Compare multiple GIS curves…” opens a table for explicitly selecting up to eight
curves from the current dataset in one MD interval. Each row shows its original
unit, source, sample and missing counts, shallowest and deepest measured depths
at stored MD precision, and value range, or the reason it is blocked. This snapshot
does not establish continuous coverage, calibration or fluid type.
Select a reviewed row to see up to ten missing sample depths at their stored MD
precision in source row order and the total missing count below the table. The
list shows individual source points. The dialog distinguishes an interval with
no rows from one with rows and no missing values. Scroll the list if it does
not fit in the window.
The comparison runs in the background with preparation, curve count, source recheck
and completion states. Cancel discards partial results and stops after the current
non-interruptible stage. The selected arrays and axis are temporarily copied, so
large LAS files require additional memory. Detected source changes reject the
result; run the review again after any edit.

**Operator dialog:** Calculations → GIS: review one sample…
(`GisReferenceDialog`, `petro_reference.action`). Select the active GIS dataset,
method and curve; enter calibration/tool IDs, reviewer, evidence, MD bounds
and parameters. Choose the source row (from 1), then click Evaluate sample.
The source preview and sample result show the selected row's MD at the stored
axis precision. The calculation uses the measurement from that row directly.
Scroll the result if it does not fit in the window.
The dialog also accepts a new gas-dataset copy containing a row-matched external
GIS curve with matching import manifest and semantic binding. Interpolated curves
and older copies without semantic bindings are not accepted automatically; retain
the originals and insert again to make a new copy. Row matching alone does not
verify geological alignment.
In the report's “Compare gas with geology” window, an operator can select a gas
interval and open “Review GIS in selected interval…” when suitable GIS exists in
the same dataset. Bounds come from a freshly rechecked gas candidate; the operator
chooses the method and curve. This preview adds no automatic conclusion or PDF content.
Use a decimal dot or comma without thousands separators. The dialog displays
source MD/value/unit, result, QC and calibration ID. Editing a field clears the
result; changing the method clears parameters. Close leaves the project unchanged.
Separate JSON records save parameters, not an active calibration, a derived curve or fluid identification.
Invalid fields, NaN, stale sources and incompatible units block calculation.
Synthetic numerical checks do not replace tool/regional field acceptance.

## Saving and opening parameters

After a successful sample evaluation, click **Save parameters…** and choose a separate JSON file.
The record contains the selected method and curve, calibration/tool IDs, reviewer,
evidence, MD bounds and method parameters. It is an independent file: saving the
project does not automatically include it, and source LAS files and samples are unchanged.
Choose a separate output JSON; the source LAS cannot be used as the record destination.

**Open parameters…** compares the record's source with the current dataset: dataset/axis/curve
identities, units, alignment evidence and actual data. A match fills the fields;
neither the result nor an active calibration is restored automatically. The record does not
save the source-row selection; the current row remains selected. Review the
parameters and source row, then explicitly click Evaluate sample. Editing fields
clears the prior verification status. Malformed records, changed sources and foreign
datasets are rejected without partially filling fields. Cancelling file selection
preserves the current inputs.

A reopened saved project can use the record if its source remains unchanged. A new
dataset copy or fresh LAS import with new identifiers does not acquire calibration
automatically, even when the numbers match. A source match does not establish tool
applicability, expert evidence or a geological conclusion. An archived JSON is not a
digital signature; accept records only from a known source.

**GIS source inventory:** click Source GIS inventory in the same dialog.
The separate table shows source IDs, units, finite paired MD/value sample
counts, **actual measured** MD bounds and QC issues. Each range is shown from
shallowest to deepest at the stored MD precision, even when the source rows are
in descending order. The bounds are equal for one finite pair. An em dash shows
that bounds are unavailable. In a small window, scroll the table horizontally
to read the full range. The axis header shows the original direction, including
bottom-up decreasing MD. Duplicate and
non-monotonic axes are flagged rather than sorted; NULLs are not
interpolated. Each opening rechecks the current source without changing
LAS, the project or entered calibration. This does not certify continuous
coverage, calibration, saturation or productivity.

## Gamma ray: IGR

`gamma_ray_index` (`igr-linear-1`): `IGR = (GR - GRclean) / (GRshale - GRclean)`. All three inputs must use the same verified API scale; `GRshale > GRclean`. **Synthetic**, not field, reference example: `GR=65`, `GRclean=25`, `GRshale=125` API → `IGR=0.4` v/v. IGR is **not automatically Vsh**: mineralogy, facies and local reference endpoints need verification. Values outside [0,1] are retained with `outside_reference_range` rather than clipped.

The separate `evaluate_gis_vsh_profile` API (module `gis_vsh_profile`) requires explicit selection of `vsh-gr-linear-1`, a separate reviewer and evidence supporting a linear relationship between GR and shale volume. Vsh = IGR only under that selected model. The source IGR calibration, local API endpoints and MD scope remain mandatory; numerical equality does not make the methods identical. Actual rows, missing values, unclipped results and QC are preserved; an out-of-reference result is not a usable physical fraction. Do not apply automatically to radioactive carbonates or unverified mineralogy. Data-only snapshot, not a new curve, UI/export or field acceptance.

## Density porosity

`density_porosity` (`density-porosity-1`): `phiD = (rho_matrix - rho_bulk) / (rho_matrix - rho_fluid)`. Densities must be explicitly supplied in g/cm³, with `rho_matrix > rho_fluid > 0`. Synthetic example: `rho_bulk=2.42`, `rho_matrix=2.71`, `rho_fluid=1.0` → `phiD≈0.16959` v/v. Negative or greater-than-one results are retained with `outside_physical_range`, not replaced with zero. Matrix density must not be guessed without rock evidence.

## Archie water saturation

`archie_water_saturation` (`archie-water-saturation-1`): `Sw = (a * Rw / (phi**m * Rt))**(1/n)`. Explicit `phi` (0 < φ ≤ 1), `Rt` and `Rw` (ohm·m), `a`, `m`, `n` (>0) are required. Synthetic example: `phi=0.2`, `Rt=10`, `Rw=0.1`, `a=1`, `m=2`, `n=2` → `Sw=0.5` v/v. Apply the equation only after checking reservoir type, water, temperature and coefficients. `Sw>1` is retained as `outside_physical_range` and does not establish fluid type.

## Quality control and next steps

`valid` means only that the numerical result is admissible for the **supplied** inputs; it does not certify calibration or producibility. Non-finite, zero and inconsistent inputs raise `ValueError`; there are no implicit coefficients, oil/gas cutoffs or LAS value translations. IGR and density-porosity interval reference profiles are available through the API; their tablet display, Vsh/Sw profiles, combined GIS/GTI/LBA correlation and independent petrophysical/field acceptance remain separate stages. Original sample values and LAS mnemonics remain unchanged. See the [plan](../PROJECT_PLAN.md) and [requirements](../REQUIREMENTS.md).

Before entering calibration, use **Review selected source** after selecting a method and curve. The review explains axis, channel identity/state, family and unit-scale blockers. Passing source checks is not calibration or interpretation approval. Repeat the review after source changes; method/channel changes clear it, and evaluation rechecks the live source. Entered evidence is preserved.

Select the source row beside the method and curve, then review the source to see its actual MD, value and original unit before calibration. The preview uses exactly that row, including descending acquisition order. Missing/non-finite or removed samples are unavailable; no neighboring value is substituted. Changing the selection clears the preview; repeat review to read current data.


## Interval reference profile (data-only)

`evaluate_gis_reference_profile(dataset, calibration, md_top_m=..., md_base_m=...)` uses an existing explicit IGR or density-porosity calibration. The closed MD interval must be inside its scope. Results contain actual rows in source order, including descending MD, original index, MD, source value and scalar QC. NaN/Inf are missing, not zero; invalid finite measurements retain their source value without an estimate. Unclipped out-of-range estimates retain their QC and are not usable fractions. An empty interval is not a zero result. The entire live source is verified before and after calculation; changed sources reject the profile. No project/LAS edits, curve insertion or interpolation. IGR is not Vsh, and Archie and field validation remain separate.

### Operator profile preview

On the IGR, density porosity, Vsh and Archie tracks, the upper and lower MD labels
preserve the exact displayed interval limits. These are the profile limits in a
preview and the current viewport limits in the temporary tablet panel. Equal
profile limits use one MD label.

In `GisReferenceDialog`, select a method and source curve, enter calibration identity, parameters and MD bounds. Click “Calculate profile…” (`petro_reference.calculate_profile`). A separate read-only UI shows original row (1-based), MD, source value, v/v estimate and QC. The selected scalar row does not control the profile. At most 10,000 rows per preview: narrow the interval if exceeded; no partial result. Recalculate after source edits. No derived curves, project saving or report approval. The API row limit (`max_rows`) is optional; the main tablet display remains separate. A depth track beside the preview table displays exact estimates as unconnected points, MD increasing down. The fraction scale includes 0–1 and expands for actual outliers; missing and invalid rows have distinct marks in a left gutter, without a value coordinate. Selecting a table row highlights its MD. The track does not establish continuous coverage, create a curve or persist in the project.

From the main-menu calculation dialog, select a profile row and click “Open selected depth in tablet…” (`petro_reference.profile_open_tablet`). Both dialogs close; the main tablet navigates to the MD interval and exact selected row (even a missing value), enabling the existing cursor. A singleton retains the viewport scale. Only the same well, dataset and original MD axis are allowed after source revalidation. TVD/TIME or a stale source blocks navigation. Only normal tablet viewport/cursor settings change, not LAS, curves or track composition. The separate “Show profile in tablet…” action opens a temporary read-only companion panel on the right, with its own labeled MD scale synchronized to the viewport and exact cursor depth. It is not a saved form track and is not exported or printed. The snapshot is discarded on source, axis, well or dataset change, or a full rebuild; validation occurs on navigation and once per second. Closing the panel does not edit the project. Recalculate to reopen.


In the separate Vsh operator preview, select an actual row and choose “Show profile in tablet…”. Only the explicitly reviewed linear Vsh is handed to the temporary companion panel, with its model, reviewer and evidence displayed. Exact points, missing values, QC, MD viewport and cursor retain their meaning. This is not IGR, a saved curve, an applicability approval or a printed track. Source or axis changes discard the stale snapshot.


### Live GIS source binding for Archie (data-only)

`evaluate_gis_archie_sources` takes **two explicitly selected curves in one native GIS dataset** sharing a verified metre-MD axis, with original v/v porosity and ohm.m resistivity units. It checks semantic bindings, provenance, current states, curve identity and exact rows. Independent evidence is required for *effective* porosity, *true* Rt, MD co-registration, Rw at formation temperature and Archie applicability. An NPHI mnemonic does not certify effective porosity; generic resistivity does not certify Rt. No percent conversion, cross-run merging, interpolation, guessed coefficients or fluid typing is performed. Full live arrays and source metadata are rechecked before publication, including changes outside the selected interval. No LAS/project edits or derived curves. This calculation API is also used by the existing Archie operator dialog; independent field acceptance has not been performed.



The separate “Archie calculation: separate preview…” action in the GIS dialog requires explicit φ (v/v) and Rt (ohm·m) curves, Rw, a/m/n, MD bounds, reviewer and independent evidence for applicability, effective porosity, true Rt and MD co-registration. The read-only table shows exact rows, source φ/Rt, unclipped Sw, missing values and QC. No default coefficients, percent conversion, cross-run join, saved curve, report export or fluid identification. Changing source values, metadata or operator inputs during the modal marks the snapshot stale. Field acceptance remains open.


The separate Archie operator preview now displays the exact numeric Rw (ohm·m), a, m and n used for the calculation. They are retained in the immutable profile rather than replaced by typical values. Parameter selection and physical applicability still require independent interpreter review; no automatic saturation approval is implied.


Intermediate Archie review now includes a standalone read-only QPainter Sw track with exact measured MD points, distinct missing/invalid markers and unclipped values beyond Sw=1. Selecting a source row highlights that row; the horizontal scale remains tied to the complete snapshot on zoom. The track is not a saved derived curve or evidence of fluid type/pay. Explicit handoff to the transient main-tablet panel is implemented; independent field acceptance remains outstanding.


A preparatory Archie Sw handoff seal now binds a reviewed exact-row snapshot to one native GIS MD axis, source φ/Rt channels, chosen row, metadata, versions and complete array bytes. Any source/axis replacement, value change or foreign dataset invalidates the seal. The live source seal is used by the existing explicit main-tablet handoff action; no saved derived curve is created. Independent interpreter model and field acceptance remain required.


Current UI: only an explicit action on a selected exact Archie row may show the source-sealed Sw snapshot as a temporary main-tablet QPainter panel. Native φ/Rt/MD fingerprints and active well/dataset/layout/axis are rechecked at handoff and on subsequent panel updates; the panel is removed upon staleness. No saved LAS-derived curve or automatic fluid/pay interpretation; field acceptance remains open.


Archie-to-tablet validation now uses the same UOM dictionary as Archie calculation: exact numerically equivalent spellings of v/v (vol/vol, cm3/cm3) and ohm.m (ohm-m, ом.м) require no numeric conversion. Percent, scaled resistivity and unknown units are never silently reinterpreted. Physical field acceptance still requires independent core/source-log and formation-temperature Rw evidence.


**Field status:** CI success or a preliminary Sw profile does not validate Archie applicability to a real well. For independent review of source logs, φeff, true Rt, formation-temperature Rw, a/m/n and responsible petrophysical sign-off, see the [Archie field-acceptance protocol](ARCHIE_FIELD_ACCEPTANCE.md).
