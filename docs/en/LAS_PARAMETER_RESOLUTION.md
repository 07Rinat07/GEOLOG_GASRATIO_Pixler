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

## Ambiguity

If two curves match one parameter with equal confidence, the application does not choose one at
random. The resolver reports a conflict and requires an explicit selection. This is important for
backup gas channels, repeated passes, and multiple sensors of the same type.

## Import

The original mnemonic is always preserved. `canonical_mnemonic` is populated only when confidence
is sufficient. Lossless source handling and export therefore retain the vendor name, while
calculations, forms, and the log display can use the canonical parameter meaning.
