from __future__ import annotations

import json
from pathlib import Path
from urllib.request import Request, urlopen


ROOT = Path(__file__).resolve().parents[1]


def _read(path: str) -> str:
    return (ROOT / path).read_text(encoding="utf-8")


def _write(path: str, content: str) -> None:
    (ROOT / path).write_text(content, encoding="utf-8", newline="\n")


def _ensure_replace(content: str, old: str, new: str, *, label: str) -> str:
    if new in content:
        return content
    count = content.count(old)
    if count != 1:
        raise RuntimeError(f"{label}: expected one anchor, found {count}")
    return content.replace(old, new, 1)


def _wheel_hash(project: str, version: str, filename: str) -> str:
    request = Request(
        f"https://pypi.org/pypi/{project}/{version}/json",
        headers={"User-Agent": "GEOLOG-GASRATIO-Pixler release-lock finalizer"},
    )
    with urlopen(request, timeout=30) as response:  # noqa: S310 - fixed HTTPS host
        payload = json.load(response)
    if payload.get("info", {}).get("version") != version:
        raise RuntimeError(f"PyPI returned an unexpected {project} version")
    matches = [item for item in payload.get("urls", []) if item.get("filename") == filename]
    if len(matches) != 1:
        raise RuntimeError(f"Expected one PyPI file {filename}, found {len(matches)}")
    digest = matches[0].get("digests", {}).get("sha256")
    if not isinstance(digest, str) or len(digest) != 64:
        raise RuntimeError(f"Missing SHA-256 for {filename}")
    return digest


def _patch_main_window() -> None:
    path = "src/geoworkbench/ui/main_window.py"
    content = _read(path)
    content = _ensure_replace(
        content,
        "from geoworkbench.ui.header_preview_widget import render_header_preview_pixmap\n",
        "from geoworkbench.ui.header_preview_widget import render_header_preview_pixmap\n"
        "from geoworkbench.ui.file_workspace_widget import FileWorkspaceWidget\n",
        label="Files workspace import",
    )
    content = _ensure_replace(
        content,
        "        self.tabs = QTabWidget()\n",
        "        self.tabs = QTabWidget()\n"
        "        self.file_workspace = FileWorkspaceWidget(\n"
        "            language=self.language.value\n"
        "        )\n",
        label="Files workspace construction",
    )
    content = _ensure_replace(
        content,
        '        self.tabs.addTab(self.tablet_view, self._t("tab.tablet"))\n',
        '        self.tabs.addTab(self.tablet_view, self._t("tab.tablet"))\n'
        "        self.tabs.addTab(\n"
        "            self.file_workspace,\n"
        "            FileWorkspaceWidget.tab_title(self.language.value),\n"
        "        )\n",
        label="Files workspace tab",
    )
    content = _ensure_replace(
        content,
        "        view_menu.addAction(self.workspace_action)\n"
        "        view_menu.addSeparator()\n",
        "        view_menu.addAction(self.workspace_action)\n"
        "\n"
        "        self.file_workspace_action = QAction(\n"
        "            FileWorkspaceWidget.tab_title(self.language.value), self\n"
        "        )\n"
        "        self.file_workspace_action.setObjectName(\"fileWorkspaceAction\")\n"
        "        self.file_workspace_action.setShortcut(\"Ctrl+Alt+F\")\n"
        "        self.file_workspace_action.setIcon(\n"
        "            self.style().standardIcon(QStyle.StandardPixmap.SP_FileDialogListView)\n"
        "        )\n"
        "        self.file_workspace_action.triggered.connect(self.show_file_workspace)\n"
        "        file_menu.addAction(self.file_workspace_action)\n"
        "        view_menu.addAction(self.file_workspace_action)\n"
        "        view_menu.addSeparator()\n",
        label="Files workspace action",
    )
    content = _ensure_replace(
        content,
        "    def _show_workspace(self, widget: QWidget | None = None) -> None:\n"
        "        self._workspace_controller.show_workspace(widget)\n"
        "\n"
        "    def _create_toolbar(self) -> None:\n",
        "    def _show_workspace(self, widget: QWidget | None = None) -> None:\n"
        "        self._workspace_controller.show_workspace(widget)\n"
        "\n"
        "    def show_file_workspace(self) -> None:\n"
        "        self.tabs.setCurrentWidget(self.file_workspace)\n"
        "        self.central_stack.setCurrentWidget(self.tabs)\n"
        "        self.statusBar().showMessage(\n"
        "            FileWorkspaceWidget.tab_title(self.language.value)\n"
        "        )\n"
        "\n"
        "    def _create_toolbar(self) -> None:\n",
        label="Files workspace navigation",
    )
    content = _ensure_replace(
        content,
        '        self.tabs.setTabText(2, self._t("tab.tablet"))\n',
        '        self.tabs.setTabText(2, self._t("tab.tablet"))\n'
        "        self.tabs.setTabText(\n"
        "            3, FileWorkspaceWidget.tab_title(self.language.value)\n"
        "        )\n"
        "        self.file_workspace_action.setText(\n"
        "            FileWorkspaceWidget.tab_title(self.language.value)\n"
        "        )\n",
        label="Files workspace retranslation",
    )
    _write(path, content)


def _patch_release_lock() -> None:
    path = "requirements/release.lock"
    content = _read(path)
    pillow_digest = _wheel_hash(
        "Pillow",
        "12.3.0",
        "pillow-12.3.0-cp311-cp311-win_amd64.whl",
    )
    pymupdf_digest = _wheel_hash(
        "PyMuPDF",
        "1.28.0",
        "pymupdf-1.28.0-cp310-abi3-win_amd64.whl",
    )
    pillow_block = (
        "pillow==12.3.0 \\\n"
        f"    --hash=sha256:{pillow_digest}\n"
        "    # via geolog-gasratio-pixler\n"
    )
    pymupdf_block = (
        "pymupdf==1.28.0 \\\n"
        f"    --hash=sha256:{pymupdf_digest}\n"
        "    # via geolog-gasratio-pixler\n"
    )
    if "pillow==12.3.0" not in content:
        anchor = "pydantic==1.10.26 \\\n"
        if content.count(anchor) != 1:
            raise RuntimeError("Pillow lock insertion anchor is missing")
        content = content.replace(anchor, pillow_block + anchor, 1)
    if "pymupdf==1.28.0" not in content:
        anchor = "pyqtgraph==0.14.0 \\\n"
        if content.count(anchor) != 1:
            raise RuntimeError("PyMuPDF lock insertion anchor is missing")
        content = content.replace(anchor, pymupdf_block + anchor, 1)
    _write(path, content)


def main() -> int:
    _patch_main_window()
    _patch_release_lock()
    print("Finalized Files workspace integration and Windows release lock")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
