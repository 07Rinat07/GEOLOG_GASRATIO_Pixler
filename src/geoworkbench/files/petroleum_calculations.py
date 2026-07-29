from __future__ import annotations

from dataclasses import dataclass
import math

from geoworkbench.files.engineering import EngineeringCalculator

_GRAVITY_M_S2 = 9.80665
_PASCAL_PER_PSI = 6_894.757293168


@dataclass(frozen=True, slots=True)
class PipeGeometry:
    outer_diameter_mm: float
    inner_diameter_mm: float
    flow_area_mm2: float
    capacity_l_per_m: float
    metal_area_mm2: float
    mass_kg_per_m: float
    total_mass_kg: float


@dataclass(frozen=True, slots=True)
class HydrostaticResult:
    pressure_mpa: float
    pressure_psi: float
    gradient_kpa_per_m: float


@dataclass(frozen=True, slots=True)
class AnnularResult:
    volume_m3: float
    volume_l: float
    capacity_l_per_m: float


@dataclass(frozen=True, slots=True)
class FormationElevationResult:
    top_elevation_m: float
    bottom_elevation_m: float
    vertical_thickness_m: float


def parse_inches(value: str) -> float:
    """Parse decimal, mixed or unicode-fraction inch notation."""

    cleaned = value.strip().replace('"', "").replace("″", "")
    inches = EngineeringCalculator().evaluate(cleaned)
    if inches <= 0:
        raise ValueError("Диаметр должен быть больше нуля")
    return inches


def pipe_geometry(
    outer_diameter_inches: str | float,
    wall_thickness_mm: float,
    length_m: float = 1.0,
    material_density_kg_m3: float = 7_850.0,
) -> PipeGeometry:
    inches = (
        parse_inches(outer_diameter_inches)
        if isinstance(outer_diameter_inches, str)
        else float(outer_diameter_inches)
    )
    outer_mm = inches * 25.4
    if wall_thickness_mm < 0:
        raise ValueError("Толщина стенки не может быть отрицательной")
    if length_m < 0:
        raise ValueError("Длина не может быть отрицательной")
    if material_density_kg_m3 <= 0:
        raise ValueError("Плотность материала должна быть больше нуля")
    inner_mm = outer_mm - 2.0 * wall_thickness_mm
    if inner_mm < 0:
        raise ValueError("Толщина стенки больше радиуса трубы")
    flow_area = math.pi * inner_mm**2 / 4.0
    metal_area = math.pi * (outer_mm**2 - inner_mm**2) / 4.0
    capacity_l_per_m = flow_area / 1_000.0
    mass_kg_per_m = metal_area * 1e-6 * material_density_kg_m3
    return PipeGeometry(
        outer_diameter_mm=outer_mm,
        inner_diameter_mm=inner_mm,
        flow_area_mm2=flow_area,
        capacity_l_per_m=capacity_l_per_m,
        metal_area_mm2=metal_area,
        mass_kg_per_m=mass_kg_per_m,
        total_mass_kg=mass_kg_per_m * length_m,
    )


def hydrostatic_pressure(mud_density_kg_m3: float, tvd_m: float) -> HydrostaticResult:
    if mud_density_kg_m3 <= 0:
        raise ValueError("Плотность раствора должна быть больше нуля")
    if tvd_m < 0:
        raise ValueError("TVD не может быть отрицательной")
    pressure_pa = mud_density_kg_m3 * _GRAVITY_M_S2 * tvd_m
    return HydrostaticResult(
        pressure_mpa=pressure_pa / 1_000_000.0,
        pressure_psi=pressure_pa / _PASCAL_PER_PSI,
        gradient_kpa_per_m=mud_density_kg_m3 * _GRAVITY_M_S2 / 1_000.0,
    )


def equivalent_circulating_density(
    mud_density_kg_m3: float,
    annular_pressure_loss_mpa: float,
    tvd_m: float,
) -> float:
    if mud_density_kg_m3 <= 0:
        raise ValueError("Плотность раствора должна быть больше нуля")
    if annular_pressure_loss_mpa < 0:
        raise ValueError("Потери давления не могут быть отрицательными")
    if tvd_m <= 0:
        raise ValueError("Для ECD укажите TVD больше нуля")
    additional_density = annular_pressure_loss_mpa * 1_000_000.0 / (_GRAVITY_M_S2 * tvd_m)
    return mud_density_kg_m3 + additional_density


def annular_volume(
    hole_diameter_mm: float,
    pipe_outer_diameter_mm: float,
    interval_length_m: float,
) -> AnnularResult:
    if hole_diameter_mm <= 0 or pipe_outer_diameter_mm < 0:
        raise ValueError("Диаметры должны быть положительными")
    if pipe_outer_diameter_mm >= hole_diameter_mm:
        raise ValueError("Диаметр трубы должен быть меньше диаметра ствола")
    if interval_length_m < 0:
        raise ValueError("Длина интервала не может быть отрицательной")
    area_mm2 = math.pi * (hole_diameter_mm**2 - pipe_outer_diameter_mm**2) / 4.0
    capacity_l_per_m = area_mm2 / 1_000.0
    volume_l = capacity_l_per_m * interval_length_m
    return AnnularResult(
        volume_m3=volume_l / 1_000.0,
        volume_l=volume_l,
        capacity_l_per_m=capacity_l_per_m,
    )


def circulation_time_minutes(volume_m3: float, flow_l_s: float) -> float:
    if volume_m3 < 0:
        raise ValueError("Объём не может быть отрицательным")
    if flow_l_s <= 0:
        raise ValueError("Расход должен быть больше нуля")
    return volume_m3 * 1_000.0 / flow_l_s / 60.0


def mixed_fluid_density(
    first_volume_m3: float,
    first_density_kg_m3: float,
    second_volume_m3: float,
    second_density_kg_m3: float,
) -> float:
    values = (first_volume_m3, first_density_kg_m3, second_volume_m3, second_density_kg_m3)
    if any(value < 0 for value in values):
        raise ValueError("Объёмы и плотности не могут быть отрицательными")
    total_volume = first_volume_m3 + second_volume_m3
    if total_volume <= 0:
        raise ValueError("Суммарный объём должен быть больше нуля")
    return (
        first_volume_m3 * first_density_kg_m3
        + second_volume_m3 * second_density_kg_m3
    ) / total_volume


def formation_elevations(
    depth_reference_elevation_m: float,
    top_tvd_m: float,
    bottom_tvd_m: float,
) -> FormationElevationResult:
    if top_tvd_m < 0 or bottom_tvd_m < 0:
        raise ValueError("TVD не может быть отрицательной")
    if bottom_tvd_m < top_tvd_m:
        raise ValueError("Подошва должна быть глубже кровли")
    return FormationElevationResult(
        top_elevation_m=depth_reference_elevation_m - top_tvd_m,
        bottom_elevation_m=depth_reference_elevation_m - bottom_tvd_m,
        vertical_thickness_m=bottom_tvd_m - top_tvd_m,
    )
