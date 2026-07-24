# GEOLOG GASRATIO@Pixler 0.7.55 — top-packed curve headers

- Kept one synchronized header band so every depth plot starts on the same pixel row.
- Packed each track's parameter blocks contiguously from the top edge.
- Routed all remaining band height below the final parameter.
- Prevented sparse tracks from spreading blank gaps between scales.
- Retained internal vertical scrolling for dense tracks.
- Fixed `NameError: opened_from_projection` in the constructor action and restored lag/depth dataset restoration to its proper workflow.
- Package **0.7.55**; project format **v20**; form schema **v6**; tablet layout **v16**.

## Verification

- focused: **86 passed**;
- headless: **1064 passed, 4 skipped, 4 deselected**;
- `compileall`: passed;
- Windows/PySide6 visual smoke test: required.
