from __future__ import annotations

from time import perf_counter

import numpy as np

from geoworkbench.tablet.sampling import select_visible_samples


def main() -> None:
    count = 2_000_000
    depth = np.linspace(0.0, 20_000.0, count)
    values = np.sin(depth / 30.0)
    values[count // 2] = 1000.0
    started = perf_counter()
    sampled_values, _ = select_visible_samples(depth, values, 0.0, 20_000.0)
    elapsed = perf_counter() - started
    zoom_started = perf_counter()
    zoom_values, _ = select_visible_samples(depth, values, 9_995.0, 10_005.0)
    zoom_elapsed = perf_counter() - zoom_started
    print(
        f"source={count} rendered={sampled_values.size} "
        f"peak={float(np.max(sampled_values)):g} elapsed={elapsed:.4f}s "
        f"zoom_rendered={zoom_values.size} zoom_elapsed={zoom_elapsed:.4f}s"
    )


if __name__ == "__main__":
    main()
