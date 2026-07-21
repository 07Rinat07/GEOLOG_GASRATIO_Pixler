# LAS Editor

Version: 0.7.6

The main interface contains a separate **Editor** section and a visible
**LAS Editor** button (`Ctrl+Alt+E`). It combines LAS creation, table editing,
depth repair, resampling, curve insertion and file splicing.

## Source-file safety

The editor never overwrites source LAS files. Repair, resampling, insertion and
splicing create an independent dataset and a new `.las` file. Source path,
encoding, SHA-256 and operation provenance are retained in metadata or manifests.

## Operations

- **Create new LAS** — range, step, MD/TVD/TVDSS index, LAS 1.2/2.0 and NULL.
- **Open LAS** — import one or more files into isolated well workspaces.
- **Edit data table** — edit values, headers and curves before exporting a new copy.
- **Repair descending depth** — reverse depth, indexes and all curves together.
- **Change depth step** — create a new copy at 0.2, 0.5, 1 m or a custom step.
- **Insert data from LAS** — select curves from an external file and map them by depth.
- **Splice LAS files** — combine depth sections with preserve-target, prefer-source or
  keep-both overlap policies.
- **Save current as new LAS** — export the current working dataset.

## Vendor and legacy cases

Descending depth, negative `STEP`, CP866/Windows-1251 input, duplicate mnemonics
and Cyrillic labels are supported. Source labels remain visible, while safe output
names are suggested: `GK:1 → GK_1` and `КС, ННК/ДСР → KS_NNK_DSR`.
