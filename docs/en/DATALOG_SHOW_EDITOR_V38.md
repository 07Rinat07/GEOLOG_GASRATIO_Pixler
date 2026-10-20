# Independent DataLog / MOL oil shows — v38 editor

**Status:** developed in a PR, not yet part of stable `main`.

Both the unified cuttings editor and the Sample Analysis window have an independent DataLog table containing nine methods: odour; visible stain; direct UV+ fluorescence; daylight and UV+ solvent cut; daylight and UV+ post-cut residue; and daylight and UV+ capillary extract.

For each method an operator can capture target-lithology coverage (% where relevant), colour, brightness/strength, distribution, reaction speed, notes and quality state (Unchecked, Verified, Suspect). An empty field is **unmeasured**, not zero. This first iteration supports one observation per method per sample; repeated readings need a later schema extension.

**Historical Florovskaya LBA fields remain unchanged.** Opening a v37 project leaves the new table empty; legacy cut/residue and the 1–5 LBA score are not silently converted to independent DataLog tests. New observations persist in **project format v38**, which older releases may not open. Back up production projects before upgrading. Automated save/open compatibility testing does not replace field acceptance.

This editor **does not** classify oil, gas or water, calculate saturation/porosity, or depth-fuse shows with GIS/mud-gas data. Next steps: verified MD alignment, gas-lag control, source/QC linkage, calibrated GIS petrophysics and geologist-approved interpretation.

Do not evaluate H₂S by smell. Check drilling-fluid background, mud additives, coal and mineral fluorescence.
