# LAS gas coverage receipt — project plan increment

After daily LAS growth or filling existing gaps, the persisted-result receipt reports raw gas coverage for the entire updated dataset: TG, C1–C5 and separate normal/isomer channels. It identifies the resolved source mnemonic, populated rows and the active-index coordinate of the last finite measurement. Zero is a measurement; NaN and infinity are missing. Ambiguous sources are distinguished from absent measurements. Locally calculated curves are excluded from raw source resolution.

The receipt warns when existing gas-ratio or TG_CALC curves are stale and asks the user to repeat the standard Gas Ratio / Haworth / Pixler calculation. It does not overwrite measurements or run calculations automatically. Coverage describes the current dataset, not values necessarily received in the latest file.

Validation: resolver aliases, ambiguous sources, zero/nonfinite handling, descending index, exclusion of calculated sources, stale ratio warning and Russian/Kazakh/English receipts. Integration requires all Windows quality, GUI/HiDPI/PDF and security checks on the PR head to succeed.

Next: a dedicated review of updated gas results after an explicit recalculation, including complete-profile coverage for the report. Manual backups remain opt-in; this increment introduces no scheduling or automatic copies.
