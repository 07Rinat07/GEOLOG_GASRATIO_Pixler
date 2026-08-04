# Real tablet PDF regression

The regression is based on the Windows diagnostics bundle created on 2026-08-04 and the corresponding BLData and GeoScape II PDFs.

Required behavior:

- A complex eight-column LAS/depth tablet exports through `QPdfWriter` at 300 DPI without a generic renderer failure.
- A time-domain tablet follows the same export path.
- The last automatic page retains a material graph body instead of collapsing to a narrow strip.
- The repeated form/curve legend is present at the bottom of the final page.
- Graph pixels are never vertically resampled merely to force a legend into a page; pagination must reserve the legend space.
