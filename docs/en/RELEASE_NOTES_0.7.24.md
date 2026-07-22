# Release notes 0.7.24 — black-tablet test hotfix

## Fix

In 0.7.23, the full-size translucent annotation `QWidget` could fail to composite with native PyQtGraph viewports on Windows and cover the tablet body with a black rectangle.

In 0.7.24, the overlay starts with an empty native region and expands only to actual visible annotation, leader, and resize-handle bounds. The region is also intersected with the graph body below the headers.

## Preserved behavior

- one OOP pointer-event router;
- permanent mouse transparency of the paint overlay;
- track editing;
- annotation creation, selection, drag, and resize;
- 0.7.23 project compatibility.

## Verification status

Unit and source-level tests run in the container. Real Windows GUI rendering is unavailable because PySide6 and pyqtgraph are not installed, so this archive is explicitly a test build.
