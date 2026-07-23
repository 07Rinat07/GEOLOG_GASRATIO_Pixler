from __future__ import annotations

from geoworkbench.printing.printer_gate import (
    PrinterCapabilities,
    PrinterGateRequest,
    PrinterGateSeverity,
    evaluate_physical_printer_gate,
)


def _capabilities(**changes) -> PrinterCapabilities:
    values = dict(
        printer_name="Engineering Plotter",
        valid=True,
        state="Idle",
        supports_custom_page_sizes=True,
        supported_page_sizes_mm=((210.0, 297.0), (297.0, 420.0)),
        supported_resolutions=(300, 600),
        minimum_page_size_mm=(100.0, 100.0),
        maximum_page_size_mm=(914.0, 5000.0),
        minimum_margins_mm=(5.0, 5.0, 5.0, 5.0),
        printable_size_mm=(200.0, 287.0),
    )
    values.update(changes)
    return PrinterCapabilities(**values)


def _request(**changes) -> PrinterGateRequest:
    values = dict(
        page_format="a4",
        page_size_mm=(210.0, 297.0),
        margins_mm=(10.0, 10.0, 10.0, 10.0),
        requested_dpi=300,
        page_count=1,
    )
    values.update(changes)
    return PrinterGateRequest(**values)


def test_supported_a4_passes_physical_gate() -> None:
    gate = evaluate_physical_printer_gate(_request(), _capabilities())

    assert gate.ok
    assert gate.selected_dpi == 300
    assert not gate.errors


def test_custom_and_roll_media_require_driver_support() -> None:
    gate = evaluate_physical_printer_gate(
        _request(page_format="roll", page_size_mm=(300.0, 1200.0)),
        _capabilities(supports_custom_page_sizes=False),
    )

    assert not gate.ok
    assert {issue.code for issue in gate.errors} == {"custom-media-unsupported"}


def test_custom_media_is_checked_against_physical_bounds() -> None:
    gate = evaluate_physical_printer_gate(
        _request(page_format="custom", page_size_mm=(1000.0, 1200.0)),
        _capabilities(),
    )

    assert not gate.ok
    assert any(issue.code == "custom-media-too-large" for issue in gate.errors)


def test_requested_resolution_is_replaced_by_nearest_supported_value() -> None:
    gate = evaluate_physical_printer_gate(
        _request(requested_dpi=360),
        _capabilities(),
    )

    assert gate.ok
    assert gate.selected_dpi == 300
    warning = next(issue for issue in gate.warnings if issue.code == "resolution-adjusted")
    assert warning.severity is PrinterGateSeverity.WARNING


def test_margins_below_printer_minimum_block_output() -> None:
    gate = evaluate_physical_printer_gate(
        _request(margins_mm=(2.0, 10.0, 10.0, 10.0)),
        _capabilities(),
    )

    assert not gate.ok
    assert any(issue.code == "minimum-margins" for issue in gate.errors)


def test_continuation_job_records_feed_warning() -> None:
    gate = evaluate_physical_printer_gate(
        _request(page_count=7),
        _capabilities(),
    )

    assert gate.ok
    assert any(issue.code == "page-continuation" for issue in gate.warnings)


def test_invalid_or_aborted_printer_is_blocked() -> None:
    gate = evaluate_physical_printer_gate(
        _request(),
        _capabilities(valid=False, state="Aborted"),
    )

    assert not gate.ok
    assert {issue.code for issue in gate.errors} >= {"printer-invalid", "printer-state"}


def test_selected_page_count_matches_system_dialog_range() -> None:
    from geoworkbench.printing.printer_gate import selected_page_count

    assert selected_page_count(8, 0, 0) == 8
    assert selected_page_count(8, 3, 5) == 3
    assert selected_page_count(8, 20, 6) == 3


def test_printable_area_smaller_than_requested_content_is_blocked() -> None:
    gate = evaluate_physical_printer_gate(
        _request(),
        _capabilities(printable_size_mm=(180.0, 260.0)),
    )

    assert not gate.ok
    assert any(issue.code == "printable-area" for issue in gate.errors)


def test_custom_bounds_accept_rotated_driver_limits() -> None:
    gate = evaluate_physical_printer_gate(
        _request(page_format="custom", page_size_mm=(1200.0, 300.0)),
        _capabilities(
            maximum_page_size_mm=(5000.0, 914.0),
            printable_size_mm=(1180.0, 280.0),
        ),
    )

    assert gate.ok
