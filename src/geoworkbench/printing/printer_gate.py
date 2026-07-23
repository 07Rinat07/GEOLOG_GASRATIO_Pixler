from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from math import isfinite


class PrinterGateSeverity(StrEnum):
    ERROR = "error"
    WARNING = "warning"


@dataclass(frozen=True, slots=True)
class PrinterGateIssue:
    code: str
    severity: PrinterGateSeverity
    message: str


@dataclass(frozen=True, slots=True)
class PrinterCapabilities:
    printer_name: str
    valid: bool
    state: str
    supports_custom_page_sizes: bool
    supported_page_sizes_mm: tuple[tuple[float, float], ...] = ()
    supported_resolutions: tuple[int, ...] = ()
    minimum_page_size_mm: tuple[float, float] | None = None
    maximum_page_size_mm: tuple[float, float] | None = None
    minimum_margins_mm: tuple[float, float, float, float] = (0.0, 0.0, 0.0, 0.0)
    printable_size_mm: tuple[float, float] | None = None


@dataclass(frozen=True, slots=True)
class PrinterGateRequest:
    page_format: str
    page_size_mm: tuple[float, float]
    margins_mm: tuple[float, float, float, float]
    requested_dpi: int
    page_count: int


@dataclass(frozen=True, slots=True)
class PhysicalPrinterGate:
    printer_name: str
    selected_dpi: int
    page_count: int
    issues: tuple[PrinterGateIssue, ...]

    @property
    def ok(self) -> bool:
        return not any(issue.severity is PrinterGateSeverity.ERROR for issue in self.issues)

    @property
    def errors(self) -> tuple[PrinterGateIssue, ...]:
        return tuple(
            issue for issue in self.issues if issue.severity is PrinterGateSeverity.ERROR
        )

    @property
    def warnings(self) -> tuple[PrinterGateIssue, ...]:
        return tuple(
            issue for issue in self.issues if issue.severity is PrinterGateSeverity.WARNING
        )


def selected_page_count(
    total_pages: int, from_page: int | None = None, to_page: int | None = None
) -> int:
    """Return the deterministic number of pages selected by a print dialog."""

    if isinstance(total_pages, bool) or not isinstance(total_pages, int) or total_pages < 1:
        raise ValueError("total page count must be a positive integer")
    start = int(from_page or 0)
    end = int(to_page or 0)
    if start <= 0 or end <= 0:
        return total_pages
    start = min(max(1, start), total_pages)
    end = min(max(1, end), total_pages)
    if end < start:
        start, end = end, start
    return end - start + 1


def evaluate_physical_printer_gate(
    request: PrinterGateRequest,
    capabilities: PrinterCapabilities,
    *,
    tolerance_mm: float = 1.0,
) -> PhysicalPrinterGate:
    issues: list[PrinterGateIssue] = []
    if not capabilities.valid:
        issues.append(_error("printer-invalid", "Selected printer is not valid"))
    if capabilities.state.casefold() in {"error", "aborted"}:
        issues.append(
            _error("printer-state", f"Printer state does not allow output: {capabilities.state}")
        )
    if request.page_count < 1:
        issues.append(_error("page-count", "Print plan does not contain pages"))

    width, height = _size(request.page_size_mm, "requested page size")
    format_value = request.page_format.casefold()
    custom = format_value in {"custom", "roll"}
    if custom:
        if not capabilities.supports_custom_page_sizes:
            issues.append(
                _error(
                    "custom-media-unsupported",
                    "Selected printer does not report support for custom or roll media",
                )
            )
        _check_physical_bounds(issues, width, height, capabilities, tolerance_mm)
    elif capabilities.supported_page_sizes_mm and not _matches_supported_size(
        (width, height), capabilities.supported_page_sizes_mm, tolerance_mm
    ):
        issues.append(
            _error(
                "standard-media-unsupported",
                "Selected printer does not report the requested standard paper size",
            )
        )

    selected_dpi = _selected_resolution(request.requested_dpi, capabilities.supported_resolutions)
    if selected_dpi != request.requested_dpi:
        issues.append(
            _warning(
                "resolution-adjusted",
                (
                    f"Requested {request.requested_dpi} DPI is unavailable; "
                    f"{selected_dpi} DPI will be used"
                ),
            )
        )

    margins = _margins(request.margins_mm)
    minimum = _margins(capabilities.minimum_margins_mm)
    if any(
        requested + 1e-6 < required
        for requested, required in zip(margins, minimum, strict=True)
    ):
        issues.append(
            _error(
                "minimum-margins",
                "Requested margins are smaller than the printable margins reported by the printer",
            )
        )

    media_blocked = any(
        issue.code
        in {
            "custom-media-unsupported",
            "custom-media-too-small",
            "custom-media-too-large",
            "standard-media-unsupported",
        }
        for issue in issues
    )
    requested_content_width = width - margins[0] - margins[2]
    requested_content_height = height - margins[1] - margins[3]
    if requested_content_width <= 0 or requested_content_height <= 0:
        issues.append(
            _error("printable-area", "Requested margins leave no printable content area")
        )
    elif not media_blocked and capabilities.printable_size_mm is not None:
        printable_width, printable_height = _size(
            capabilities.printable_size_mm, "printer printable size"
        )
        if (
            requested_content_width - tolerance_mm > printable_width
            or requested_content_height - tolerance_mm > printable_height
        ):
            issues.append(
                _error(
                    "printable-area",
                    "Printer printable area is smaller than the requested content area",
                )
            )

    if request.page_count > 1:
        issues.append(
            _warning(
                "page-continuation",
                (
                    f"The physical job contains {request.page_count} continuation pages; "
                    "paper feed must remain available"
                ),
            )
        )

    if not capabilities.printer_name.strip():
        issues.append(_warning("printer-name", "Printer driver did not return a printer name"))

    return PhysicalPrinterGate(
        capabilities.printer_name.strip(), selected_dpi, request.page_count, tuple(issues)
    )


def _check_physical_bounds(
    issues: list[PrinterGateIssue],
    width: float,
    height: float,
    capabilities: PrinterCapabilities,
    tolerance: float,
) -> None:
    if capabilities.minimum_page_size_mm is not None:
        minimum = _size(capabilities.minimum_page_size_mm, "minimum page size")
        if not _fits_minimum_size((width, height), minimum, tolerance):
            issues.append(
                _error(
                    "custom-media-too-small",
                    "Requested custom media is below printer limits",
                )
            )
    if capabilities.maximum_page_size_mm is not None:
        maximum = _size(capabilities.maximum_page_size_mm, "maximum page size")
        if not _fits_maximum_size((width, height), maximum, tolerance):
            issues.append(
                _error(
                    "custom-media-too-large",
                    "Requested custom media exceeds printer limits",
                )
            )


def _fits_minimum_size(
    requested: tuple[float, float], minimum: tuple[float, float], tolerance: float
) -> bool:
    width, height = requested
    min_width, min_height = minimum
    return (
        width + tolerance >= min_width and height + tolerance >= min_height
    ) or (
        width + tolerance >= min_height and height + tolerance >= min_width
    )


def _fits_maximum_size(
    requested: tuple[float, float], maximum: tuple[float, float], tolerance: float
) -> bool:
    width, height = requested
    max_width, max_height = maximum
    return (
        width - tolerance <= max_width and height - tolerance <= max_height
    ) or (
        width - tolerance <= max_height and height - tolerance <= max_width
    )


def _matches_supported_size(
    requested: tuple[float, float],
    supported: tuple[tuple[float, float], ...],
    tolerance: float,
) -> bool:
    width, height = requested
    return any(
        (abs(width - candidate_width) <= tolerance and abs(height - candidate_height) <= tolerance)
        or (
            abs(width - candidate_height) <= tolerance
            and abs(height - candidate_width) <= tolerance
        )
        for candidate_width, candidate_height in supported
    )


def _selected_resolution(requested: int, supported: tuple[int, ...]) -> int:
    valid = tuple(sorted({int(value) for value in supported if int(value) > 0}))
    if not valid or requested in valid:
        return requested
    return min(valid, key=lambda value: (abs(value - requested), -value))


def _size(value: tuple[float, float], name: str) -> tuple[float, float]:
    if len(value) != 2:
        raise ValueError(f"{name} must contain width and height")
    width, height = map(float, value)
    if not isfinite(width) or not isfinite(height) or width <= 0 or height <= 0:
        raise ValueError(f"{name} must be positive and finite")
    return width, height


def _margins(value: tuple[float, float, float, float]) -> tuple[float, float, float, float]:
    if len(value) != 4:
        raise ValueError("four printer margins are required")
    margins = tuple(float(item) for item in value)
    if any(not isfinite(item) or item < 0 for item in margins):
        raise ValueError("printer margins must be finite and non-negative")
    return margins  # type: ignore[return-value]


def _error(code: str, message: str) -> PrinterGateIssue:
    return PrinterGateIssue(code, PrinterGateSeverity.ERROR, message)


def _warning(code: str, message: str) -> PrinterGateIssue:
    return PrinterGateIssue(code, PrinterGateSeverity.WARNING, message)
