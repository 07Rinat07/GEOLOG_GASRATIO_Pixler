# LAS parameter recognition and mapping

## Purpose

LAS files from different vendors often use different mnemonics, descriptions, and units for the
same physical measurement. Column order also varies and is never treated as semantic evidence.
GEOLOG GASRATIO@Pixler uses one semantic resolver that maps each source curve to a canonical
parameter.

## Evidence used

The resolver evaluates evidence in this order:

1. an explicit user mapping supplied by the workflow;
2. canonical and original mnemonics;
3. aliases from the built-in Sensors catalog;
4. chemical formulas and common forms such as `C-1`, `CH4`, `C2H6`, and `C3H8`;
5. Russian, Kazakh, or English curve descriptions;
6. unit compatibility with the inferred parameter type;
7. numeric coverage when several candidates compete.

Visually identical Latin and Cyrillic characters are normalized. For example, Cyrillic `С1` is
recognized as Latin `C1`. Case, spaces, hyphens, underscores, and common acquisition suffixes do
not affect controlled exact matching.

Chromatograph aliases also include `IBUT/IButane/C4I`, `NBUT/NButane/C4N`,
`IPENT/IPentane/C5I`, and `NPENT/NPentane/C5N`. Drilling aliases include `ROP_AVG`,
`BIT_SIZE_IN`, `BIT_DIAMETER_IN`, `BDIA`, and `DBIT`.

## Gas Ratio

Before calculation, the application resolves `C1`, `C2`, `C3`, plus available
`C4/iC4/nC4/C5/iC5/nC5` components. The previous dependency on column order and a small list of
exact names has been removed.

Concentrations can be converted to one percent scale:

- `%`, `vol%`, `%vol` — unchanged;
- `ppm/ppmv` — divided by `10000`;
- `ppb/ppbv` — divided by `10000000`;
- `fraction` or `v/v` — multiplied by `100`.

When all units are absent, the common source scale is retained. If units conflict and no safe
conversion is possible, the calculation is blocked with a clear message instead of silently
mixing incompatible quantities.

The GeoScape II manual describes seven separate chromatograph outputs: methane, ethane, propane,
isobutane, butane, isopentane, and pentane. In its legacy export, `C4+iC4` therefore means
`nC4+iC4`, while `C5+iC5` means `nC5+iC5`. The resolver treats `C4/C5` as contextual aliases
of the normal isomers without changing values or materializing a calculated curve. An explicitly
named `TOTAL_C4/TOTAL_C5` channel is not reinterpreted. Automatic fallback is also rejected when
the generic and iso curves are numerically identical. The vendor rule requires the complete
`C4+iC4` and `C5+iC5` context. Official SLB terminology independently confirms the canonical
international `C1/C2/C3/nC4/iC4/nC5/iC5` set.

## Ambiguity

If two curves match one parameter with equal confidence, the application does not choose one at
random. The resolver reports a conflict and requires an explicit selection. This is important for
backup gas channels, repeated passes, and multiple sensors of the same type.

Byte-equivalent numeric copies with compatible units are the one exception. Duplicate channels
introduced by LAS merging, such as `S106` and `S106_TEHNOLOGIYA`, collapse to one deterministic
source. A single differing value keeps the ambiguity and still requires explicit selection.

Bit size is never inferred from the file name or from the `CALI` caliper curve because these are
different physical quantities. When an actual `BIT/BS/HOLE_SIZE` value is absent from LAS, the
operator supplies diameter sections in the input configuration.

## Import

The original mnemonic is always preserved. `canonical_mnemonic` is populated only when confidence
is sufficient. Lossless source handling and export therefore retain the vendor name, while
calculations, forms, and the log display can use the canonical parameter meaning.

## Human-readable LAS table headers

The table editor uses the same resolver and defaults to a three-level header: a localized friendly
name, the source-to-canonical mapping (`S800 → C1`), and the unit. Users can select Friendly + LAS,
Friendly only, or LAS only.

The header tooltip preserves the audit trail: original mnemonic, canonical parameter, LAS
description, unit, recognition confidence, method, evidence, and provenance. An unresolved curve is
never silently renamed. Its LAS description is used when available; otherwise the column is marked
as unrecognized and requires an explicit mapping.
