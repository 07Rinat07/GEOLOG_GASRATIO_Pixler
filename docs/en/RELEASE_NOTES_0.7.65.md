# GEOLOG GASRATIO@Pixler 0.7.65 — ready forms and full save dialog

## Fixes

- **Save user form** no longer uses the small name prompt.
- **Create form** and **Save user form** show all ready, factory, and user forms, search, and the
  selected form details.
- A duplicate name is blocked case-insensitively after whitespace normalization; an editable user
  form is updated only as an explicitly confirmed new revision.
- Four known local forms are polished and atomically moved to `forms/ready`. Their actual columns,
  tracks, parameters, scales, styles, and order are preserved.
- No separate duplicate factory MASTERLOG template is added to the library.
- Geological reference columns are reduced once by **50%** with a **48 px** minimum; ordinary
  graphs and text retain an **80 px** minimum.
- form schema v7 and older migrates to **v8**; tablet layout v17 and older migrates to **v18**.

## User workflow

1. Click **Create form** or **Save user form**.
2. Review all ready and user forms, their axis, type, structure, widths, and parameters.
3. Enter an available name; duplicate and whitespace normalization is applied before validation.
4. Confirm a new revision when updating an existing editable form.
5. Press **Ctrl+S** separately for project data and inserted symbols, then close and reopen the
   project for verification.

## Important

The supplied source ZIP did not contain the four local-form JSON files. On the original computer
they are processed automatically from the application profile. Transfer them separately for a
clean computer.
