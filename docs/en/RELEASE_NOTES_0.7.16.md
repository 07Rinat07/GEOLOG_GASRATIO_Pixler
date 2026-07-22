# Release notes 0.7.16

This release adds the GeoScape/Paradox DB → unified `Dataset` model → existing editor → project/LAS/graphs/tablets flow. It includes a bounded binary reader, DB/PX/TV/FAM discovery, depth/time candidates, profiles, channel dictionary, quality control, depth/time LAS, TIME → DEPTH, batch conversion, progress, and cancellation.

Verified samples: `BLData.db` — 3488 rows/70 fields; `D250.db` — 1739/101. Source files were unchanged. The current container does not include `lasio`, so actual re-opening of generated LAS must be completed in the normal Windows environment.
