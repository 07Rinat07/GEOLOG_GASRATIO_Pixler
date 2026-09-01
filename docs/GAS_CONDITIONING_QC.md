# Gas conditioning QC provenance

## Purpose

GAS-06 makes interpolation performed by the gas-conditioning layer auditable instead of leaving restored samples as an implicit preprocessing detail.

The calculation layer produces an immutable `GasConditioningQcSummary`. The project persistence layer stores that summary directly on `Dataset.gas_conditioning_qc`; it is not encoded into LAS headers or the free-form `parameters` mapping.

## Persisted contract

Project format v24 stores the following dataset-level structure:

- `nominal_depth_step`: nominal depth cadence used by conditioning;
- `affected_depth_row_count`: number of source depth rows affected by at least one restored gas component;
- `interpolated_component_sample_count`: total restored component samples across all gas channels;
- `components`: deterministic mnemonic-sorted component QC records.

Each component record stores:

- normalized mnemonic;
- restored sample count;
- contiguous restored depth intervals with inclusive minimum/maximum depth and sample count;
- effective `max_gap` used for that component, or `null` when interpolation was not applicable.

## Calculation-session lifecycle

`ProjectSession.calculate_basic_gas_ratios()` stores the exact `calculation.conditioned_components.qc_summary` produced for the derived gas curves. The session does not reconstruct QC from the output curves and does not maintain a second set of interpolation counters.

The new summary is assigned to `Dataset.gas_conditioning_qc` only after every derived-curve `upsert_curve()` call has completed successfully. If conditioning, ratio calculation or a derived-curve write raises, the previously persisted QC summary remains unchanged instead of being replaced by provenance from a failed or partial recalculation. A successful calculation records a non-null summary even when no samples required interpolation; in that case the affected/restored counters are zero and the interval lists are empty.

## Compatibility

Project format v23 migrates to v24 by adding `gas_conditioning_qc: null` to every existing dataset. The migration is structural and does not infer historical interpolation that was never recorded.

The v24 decoder validates the nested QC object strictly and rejects malformed counts, invalid intervals, unknown keys and invalid numeric values with `ProjectFormatError`.

## Remaining GAS-06 work

The domain, persistence and calculation-session slices are implemented. A later isolated branch must expose the persisted QC summary in the operator UI/reporting path. GAS-06 should be marked complete in the canonical project plan only after that UI slice and its acceptance tests are green and merged.
