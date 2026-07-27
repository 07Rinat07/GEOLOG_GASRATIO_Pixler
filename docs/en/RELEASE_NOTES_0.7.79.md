# GEOLOG GASRATIO@Pixler 0.7.79 — WITSML 2.x ChannelSet data import

Added safe offline reading of embedded and relative-file WITSML 2.x ChannelData arrays, ChannelSet
and channel/index selection, strict UOM normalization, semantic Import Review and deterministic
Dataset provenance. The complete immutable Dataset is created before the project is changed and
the exact reviewed commit is registered once through an atomic project controller.

Invalid index rows remain visible to review and can be explicitly dropped. Unsupported scalar,
array or UOM contracts block commit instead of being guessed. XML/ZIP limits, traversal protection,
SHA-256 source/data fingerprints and a deterministic Dataset digest are retained.

Project format remains v20. The separate real-GSWITS Windows reliability gate is still open and
runs in parallel; this release only supplies its checklist and existing soak tooling.
