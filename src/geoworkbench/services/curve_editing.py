from dataclasses import dataclass
import numpy as np
from numpy.typing import NDArray

@dataclass(frozen=True, slots=True)
class DrawPoint:
    depth: float
    value: float

def interpolate_drawn_curve(depth: NDArray[np.float64], points: list[DrawPoint]) -> NDArray[np.float64]:
    if len(points)<2:
        raise ValueError("At least two points required")
    ordered=sorted(points,key=lambda p:p.depth)
    x=np.asarray([p.depth for p in ordered],dtype=np.float64)
    y=np.asarray([p.value for p in ordered],dtype=np.float64)
    if np.any(np.diff(x)<=0):
        raise ValueError("Depths must be unique")
    return np.interp(depth,x,y)
