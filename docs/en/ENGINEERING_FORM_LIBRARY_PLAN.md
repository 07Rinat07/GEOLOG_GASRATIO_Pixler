# Engineering form library

The goal is a set of ready-to-use forms that can be applied to a LAS dataset, printed, and copied into an editable user form.

## Factory forms

- Gas Ratio & Pixler;
- C1–C5 gas components;
- D-exponent and corrected D-exponent;
- drilling technology parameters;
- lithology, rock description, and cuttings log;
- calcimetry;
- LBA;
- integrated geological and technological form.

A factory form is immutable. Create copy produces an independent user form where LAS curves, calculation profiles, text, interval, lithology, cuttings, and laboratory tracks can be added. All settings persist.

## Next tasks

1. Form categories and LAS compatibility diagnostics.
2. Separate Gas Ratio, Pixler, and Haworth scales.
3. Preparation of missing derived curves before applying a form.
4. Explainable fluid markers with manual confirmation.
5. Persistence of special data and unified print/PDF output.

## Reference forms from field material

The library now targets two confirmed working scenarios:

1. A depth geological-geochemical Masterlog with stratigraphy, drilling curves, depth, cuttings,
   LBA, calcimetry, lithology, C1-C5/Total Gas and rock descriptions.
2. A time-based engineering-control form with WOB, ROP, RPM, TQ, SPP, pumps, flow, mud
   temperature, gas, depth and pit volumes.

The LBA legend is part of the editable header. Bitumen type is color-coded and intensity 1-5 uses
conventional symbols. Titles, scales, widths, order and column content are edited in a user copy of
the protected factory form and persisted.
