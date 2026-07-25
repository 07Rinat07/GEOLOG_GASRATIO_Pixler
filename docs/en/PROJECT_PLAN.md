# GEOLOG GASRATIO@Pixler project plan

Current as of 25 July 2026. Version **0.7.66** uses project format **v20**,
form schema **v8**, and tablet layout **v18**.

## Completed

- [x] use one complete registry for Form Library, create, and save workflows;
- [x] show the same Ready, **18 factory**, and user forms in every window;
- [x] make the main and F4 toolbars responsive without clipping the right-side toggle;
- [x] add **Clear diagnostics data…** with confirmation and a safe deletion scope;
- [x] automatically limit accumulated import diagnostics to the newest 30 reports;
- [x] update RU/KK/EN documentation and add regression tests.

## Next stage

- [ ] visually verify normal/compact switching on Windows at 900, 1366, 1600, and 1920 px widths
  and 100–150% scaling;
- [ ] confirm identical form membership in browse/create/save windows against the real profile;
- [ ] continue the approved project plan after user acceptance.

## Acceptance criterion

At the screenshot window width, the **Editing** caption and button remain inside the right edge.
The ordinary library shows the same 18 factory forms as the save window. After diagnostics cleanup,
logging is recreated while projects and user data remain untouched.
