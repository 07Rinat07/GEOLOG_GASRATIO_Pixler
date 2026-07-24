# GEOLOG GASRATIO@Pixler project status

Snapshot: 25 July 2026. Package version: **0.7.65**. Project format: **v20**,
form schema: **v8**, tablet layout: **v18**.

## Completed in 0.7.65

- the old small name prompt was removed from both **Create form** and **Save user form**; each
  command now shows all ready, factory, and user forms, search, and detailed structure;
- a duplicate name is blocked case-insensitively after whitespace normalization, while saving over
  an editable user form creates a new revision only after an explicit warning;
- four confirmed local forms with legacy names are polished, moved to `forms/ready`, and protected
  as ready templates without adding a separate duplicate MASTERLOG factory template;
- the actual JSON structure is preserved, including columns, tracks, parameters, scales, styles,
  and order;
- stratigraphy, lithology, cuttings, calcimetry, LBA, and depth are reduced by **50%** during
  migration with a **48 px** minimum, while other graphs retain an **80 px** minimum;
- forms at v7 or older migrate once to **v8**, and tablets at v17 or older migrate once to **v18**;
- documentation, instructions, and release notes are synchronized in Russian, Kazakh, and English.

## Verification

Model, codec/repository, migration, naming, layout/print, and source-integrity tests pass. The
automated audit checks localized document parity, Markdown links, all 1881 interface keys, package
version, graph-symbol persistence, compact widths, and the complete form creation/save workflow.
A full visual Qt/UI run requires a Windows environment with PySide6, pyqtgraph, and lasio.

## Local-form transfer limitation

The supplied source ZIP does not contain the four JSON files stored in the Windows application
profile. On the same computer they are parsed and promoted automatically. A clean installation on
another computer requires exporting or copying those JSON files from the local form library.
