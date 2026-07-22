# Release notes 0.7.19

## Annotation depth/time synchronization fixed

- Callouts and comments now remap their screen anchor whenever the visible axis range changes.
- Mouse-wheel scrolling, the vertical scrollbar, panning, go-to and zoom move an annotation together with its depth or time coordinate.
- The text box keeps the user-defined offset, width, height and styling relative to the data anchor.
- When the anchored depth leaves the visible interval, the annotation leaves the viewport with the data instead of remaining fixed over the graph.
- Curve-bound annotations recompute both coordinates: X from the parameter value and Y from the active depth/time axis.
- Position refresh does not overwrite text, style, size or persisted offsets.
- Existing annotation graphics helpers are reused during navigation instead of being rebuilt on every wheel step.

## Compatibility

The project format and `annotation` object schema are unchanged. Annotations created by versions 0.7.15–0.7.18 open without migration.

## Validation

Regression guards cover both navigation paths: the shared tablet camera and direct pyqtgraph `ViewBox` range changes.
