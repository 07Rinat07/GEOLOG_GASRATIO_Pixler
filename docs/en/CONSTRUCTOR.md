# Constructor guide

Open **Constructor → Open constructor** or press `Ctrl+Shift+K`.

The tablet-form tab opens the existing Form Manager. Rapid selection is debounced and guarded
by a revision token. Wheel pans depth, `Ctrl + wheel` zooms around the pointer, and touchpad
navigation also works over plots, headers and empty tablet areas.

The print tab provides the WYSIWYG header editor, columns, curve mapping, page and scale,
depth symbols, project images and final preview. The canvas uses millimetres. A red dashed
line shows the physical page width; content to its right will overflow.

Supported page profiles: A0–A4, Letter, Legal, custom and roll, with portrait or landscape
orientation where applicable. Header elements include text, dynamic fields, images, lines,
lithology legend and LBA legend. Images may be BMP, PNG, JPEG, TIFF, WebP or SVG and support
fit, fill, stretch, rotation and opacity.

The asset tab contains 117 lithotypes and 19 depth symbols with multilingual names, aliases,
thumbnails and checksums. Lithotypes use tiled non-smoothed patterns. Legend scopes are used,
all, manually selected, and used plus selected.

Depth symbols support point, interval, curve-parameter and time anchors. Choose the column,
parameter, image, size, label and X/Y millimetre offsets. The semantic depth anchor remains the
source of truth while offsets provide precise visual adjustment.

Run preflight before output. It checks datasets, columns, header overflow, missing resources,
curve bindings and depth-symbol validity.
