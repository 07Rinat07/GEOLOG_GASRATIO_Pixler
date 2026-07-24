# GEOLOG GASRATIO@Pixler project plan

Current as of 25 July 2026. Version **0.7.65** uses project format **v20**,
form schema **v8**, and tablet layout **v18**.

## Completed

- [x] replace the old name prompt in **Create form** and **Save user form** with one window showing
  all ready, factory, and user forms;
- [x] show search, axis, type, description, revision, columns, widths, tracks, and parameters;
- [x] block a duplicate name case-insensitively after whitespace normalization;
- [x] allow an intentional editable user-form update as a new revision;
- [x] polish four confirmed local-form names and promote their actual JSON structures to Ready;
- [x] avoid a separate duplicate MASTERLOG factory template;
- [x] reduce the requested geological columns by **50%** with a **48 px** minimum;
- [x] retain an **80 px** minimum for ordinary graphs and text;
- [x] run one-time form schema v7 → **v8** and tablet layout v17 → **v18** migrations;
- [x] synchronize RU/KK/EN documentation and cover the changes with tests.

## Next stage

- [ ] perform a visual Windows run of the new window in all three languages;
- [ ] verify the four real profile forms after automatic promotion to `forms/ready`;
- [ ] verify drag-resize, reopen, preview, PDF, and physical printing at real DPI;
- [ ] continue the approved project plan after user acceptance.

## Acceptance criterion

Saving the tablet form must not open `QInputDialog`. The user sees every occupied name and its
details before confirmation. After the first library open, the four known forms appear as Ready
with polished names, and compact widths are not reduced a second time.
