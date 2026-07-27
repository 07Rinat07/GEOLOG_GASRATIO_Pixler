# GEOLOG GASRATIO@Pixler 0.7.83 — GeoScape WITS compatibility reference

Compatibility patch 0.7.83 corrects the GSWITS standard header, moves source sequence handling from
item `02` to item `04`, and adds the complete 963-field GeoSensor WITS Level 0 catalog derived from
the supplied `GeoScape2.zip` archive.

The release also adds deterministic catalog-generation tooling, a real frame fixture from the GSWITS
manual, vendor-reference hashes, and regression coverage proving identical live/replay parsing.
Original GeoScape binaries, databases, and manuals are not redistributed in the package or wheel.
