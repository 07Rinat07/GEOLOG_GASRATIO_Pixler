# LAS gas coverage receipt — project plan increment

After daily LAS growth or filling existing gaps, the persisted-result receipt reports raw gas coverage for the entire updated dataset: TG, C1–C5 and separate normal/isomer channels. It identifies the resolved source mnemonic, populated rows and the active-index coordinate of the last finite measurement. Zero is a measurement; NaN and infinity are missing. Ambiguous sources are distinguished from absent measurements. Locally calculated curves are excluded from raw source resolution.

The receipt warns when existing gas-ratio or TG_CALC curves are stale and asks the user to repeat the standard Gas Ratio / Haworth / Pixler calculation. It does not overwrite measurements or run calculations automatically. Coverage describes the current dataset, not values necessarily received in the latest file.

Validation: resolver aliases, ambiguous sources, zero/nonfinite handling, descending index, exclusion of calculated sources, stale ratio warning and Russian/Kazakh/English receipts. Integration requires all Windows quality, GUI/HiDPI/PDF and security checks on the PR head to succeed.

## Explicit recalculation receipt — in review

The standard Gas Ratio / Haworth / Pixler action now displays and logs a receipt for the calculated dataset. It reports the number of complete positive finite C1/C2–C1/C5 profiles paired on the same row, their first and last active-index coordinates in row order, and the count of rows without a complete profile. The span is explicitly not a guarantee of continuity. Missing, stale, calculating, failed or incorrectly sized ratio curves cannot certify current profiles. The receipt preserves TIME coordinates and does not label them as depth. Source arrays remain unchanged by coverage inspection.

After calculation, regenerate the PDF to include the updated result. This receipt describes current project state and does not claim that an existing PDF has changed. Validation includes a real controller recalculation restoring a previously stale tail, active-index handling, gaps, missing profiles, all three languages and the main-window result/log integration.

Next: continue report validation on user datasets and the remaining opt-in backup restore/scheduling plan. Manual backups remain opt-in; this increment introduces no scheduling or automatic copies.


## Native plot ownership follow-up

The first Windows quality run for the recalculation receipt aborted in pyqtgraph PlotItem menu construction during dataset-merge Undo. Investigation found a separate ownership defect: PlotWidget.close() calls setParent(None), so deleting the track did not delete the detached plot. Disposal now returns the closed plot to its track parent before the existing receiver-specific DeferredDelete settlement. This releases the native plot before replacement, without pumping unrelated events or skipping the failing Undo assertions.

A regression checks that native plots are invalid after clear and after repeated full rebuilds. The new assertion fails on the previous implementation and passes with the ownership fix. This proves the orphan lifetime defect; confirmation of the Windows access-violation repair still requires all three checks on the updated head.


The main merge run 38964585485 also aborted in PlotItem menu construction, in the small track-resize test file after unrelated Qt tests in a shared process. That file now uses the existing per-function native subprocess runner. Both resize tests remain mandatory, child errors still fail the gate, and the runner contract verifies complete selection without duplication or omission. This isolates the Windows offscreen test heap; it is not a claim that every source of native Qt corruption is resolved.
