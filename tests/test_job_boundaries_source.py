from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_main_window_delegates_print_execution_to_service() -> None:
    source = (ROOT / "src/geoworkbench/ui/main_window.py").read_text(encoding="utf-8")
    service = (ROOT / "src/geoworkbench/services/print_jobs.py").read_text(encoding="utf-8")

    assert "self._print_jobs = PrintJobExecutor()" in source
    assert "self._print_jobs.create_printer" in source
    assert "self._print_jobs.render_to_printer" in source
    assert "self._print_jobs.execute_file" in source
    assert "export_document_pdf" not in source
    assert "export_document_pages" not in source
    assert "render_document_to_printer" not in source
    assert "class PrintJobExecutor" in service


def test_project_open_uses_session_binding_registry() -> None:
    source = (ROOT / "src/geoworkbench/ui/main_window.py").read_text(encoding="utf-8")
    binding = (ROOT / "src/geoworkbench/services/session_binding.py").read_text(
        encoding="utf-8"
    )
    open_project = source[source.index("    def open_project(") : source.index(
        "    def _show_current_dataset(", source.index("    def open_project(")
    )]

    assert "self._bind_project_session()" in open_project
    assert ".session = self.session" not in open_project
    assert "class SessionBindingController" in binding
    assert 'name="time_depth_mapping"' in source
    assert 'name="time_to_depth"' in source
    assert 'name="workspace_commands"' in source


def test_tree_activation_delegates_to_workspace_command_controller() -> None:
    source = (ROOT / "src/geoworkbench/ui/main_window.py").read_text(encoding="utf-8")
    commands = (ROOT / "src/geoworkbench/services/workspace_commands.py").read_text(
        encoding="utf-8"
    )
    start = source.index("    def _activate_tree_item(")
    end = source.index("    def _show_tablet_curve_in_inspector(", start)
    handler = source[start:end]

    assert "self._workspace_commands.activate(payload)" in handler
    assert "current_well_id" not in handler
    assert "current_dataset_id" not in handler
    assert "class WorkspaceCommandController" in commands
