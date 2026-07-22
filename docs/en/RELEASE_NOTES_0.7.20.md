# Release notes 0.7.20

## Unified date and time display

- Added one `DD.MM.YYYY HH:MM:SS` formatter with identical Windows and Linux behavior.
- Tablet cursor panels, the LAS table, the standalone curve view, Paradox preview, annotation editor and printable inspections no longer expose calendar time as unexplained raw seconds.
- Supports `numpy.datetime64`, Unix seconds/milliseconds, Delphi/OLE Automation dates and elapsed time.
- When a calendar index or registration start exists, elapsed values are shown as a full date/time; otherwise `HH:MM:SS` is used.
- Platform-dependent `datetime.fromtimestamp` and `utcfromtimestamp` were removed from user-facing formatting paths.

## Direct F4 annotation workflow

1. Enable F4.
2. Arm Callout, Comment or Image.
3. Click the exact track and depth/time position.
4. The object is created immediately at that point.
5. Drag the frame/background and resize with eight side/corner handles.
6. Double-click, F2, Enter, a toolbar action or the context menu opens the full editor.

The annotation overlay is now clipped to the graph body: boxes, leaders and handles cannot paint over track headers or parameter captions. New objects near the upper/lower edge are initially placed inside the visible plot.

## Compatibility

The project format and annotation schema are unchanged. Projects from 0.7.15–0.7.19 open without migration. Source LAS/DB files are never modified.
