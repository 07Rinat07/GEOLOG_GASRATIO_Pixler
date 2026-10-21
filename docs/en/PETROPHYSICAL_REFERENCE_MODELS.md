# Petrophysical reference calculations: IGR, porosity and Archie

## Purpose and availability

This guide describes isolated calculation code in PR #686 (INTERP-PETRO-01), **not a UI command**. The functions are absent from `main` until the PR is merged. `geoworkbench.services.petrophysical_reference_models` accepts previously verified scalar inputs and returns an immutable result with `method_id`, `value`, `unit`, `quality`, and `parameters`. It does not discover LAS mnemonics, convert units, align MD/TVD, or modify the project.

## Gamma ray: IGR

`gamma_ray_index` (`igr-linear-1`): `IGR = (GR - GRclean) / (GRshale - GRclean)`. All three inputs must use the same verified API scale; `GRshale > GRclean`. **Synthetic**, not field, reference example: `GR=65`, `GRclean=25`, `GRshale=125` API → `IGR=0.4` v/v. IGR is **not automatically Vsh**: mineralogy, facies and local reference endpoints need verification. Values outside [0,1] are retained with `outside_reference_range` rather than clipped.

## Density porosity

`density_porosity` (`density-porosity-1`): `phiD = (rho_matrix - rho_bulk) / (rho_matrix - rho_fluid)`. Densities must be explicitly supplied in g/cm³, with `rho_matrix > rho_fluid > 0`. Synthetic example: `rho_bulk=2.42`, `rho_matrix=2.71`, `rho_fluid=1.0` → `phiD≈0.16959` v/v. Negative or greater-than-one results are retained with `outside_physical_range`, not replaced with zero. Matrix density must not be guessed without rock evidence.

## Archie water saturation

`archie_water_saturation` (`archie-water-saturation-1`): `Sw = (a * Rw / (phi**m * Rt))**(1/n)`. Explicit `phi` (0 < φ ≤ 1), `Rt` and `Rw` (ohm·m), `a`, `m`, `n` (>0) are required. Synthetic example: `phi=0.2`, `Rt=10`, `Rw=0.1`, `a=1`, `m=2`, `n=2` → `Sw=0.5` v/v. Apply the equation only after checking reservoir type, water, temperature and coefficients. `Sw>1` is retained as `outside_physical_range` and does not establish fluid type.

## Quality control and next steps

`valid` means only that the numerical result is admissible for the **supplied** inputs; it does not certify calibration or producibility. Non-finite, zero and inconsistent inputs raise `ValueError`; there are no implicit coefficients, oil/gas cutoffs or LAS value translations. Next steps are GIS source provenance, unit and depth-axis validation, operator UI integration, and independent petrophysical/field acceptance. Original sample values and LAS mnemonics remain unchanged. See the [plan](../PROJECT_PLAN.md) and [requirements](../REQUIREMENTS.md).
