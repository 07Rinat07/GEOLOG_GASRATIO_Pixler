def next_sample_interval(
    previous_bottom: float, step: float, well_bottom: float | None = None
) -> tuple[float, float]:
    if step <= 0:
        raise ValueError("Step must be positive")
    top = previous_bottom
    bottom = top + step
    if well_bottom is not None:
        bottom = min(bottom, well_bottom)
    if bottom <= top:
        raise ValueError("No remaining interval")
    return top, bottom
