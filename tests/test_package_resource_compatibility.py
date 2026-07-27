from __future__ import annotations

from pathlib import Path

from geoworkbench.acquisition import wits0, wits0_catalog
from geoworkbench.importers.paradox import channel_dictionary
from geoworkbench.services import localization


class _SingleChildTraversable:
    """Emulate Python builds where Traversable.joinpath accepts one child only."""

    def __init__(self, path: Path) -> None:
        self._path = path

    def joinpath(self, child: str) -> "_SingleChildTraversable":
        return _SingleChildTraversable(self._path / child)

    def read_text(self, *, encoding: str) -> str:
        return self._path.read_text(encoding=encoding)


def _strict_files(package: str) -> _SingleChildTraversable:
    package_root = Path(__file__).resolve().parents[1] / "src" / "geoworkbench"
    if package == "geoworkbench.resources":
        package_root /= "resources"
    elif package != "geoworkbench":
        raise AssertionError(f"unexpected package: {package}")
    return _SingleChildTraversable(package_root)


def test_builtin_resources_support_single_child_joinpath(monkeypatch) -> None:
    monkeypatch.setattr(wits0, "files", _strict_files)
    monkeypatch.setattr(wits0_catalog, "files", _strict_files)
    monkeypatch.setattr(localization, "files", _strict_files)
    monkeypatch.setattr(channel_dictionary, "files", _strict_files)

    assert wits0.load_builtin_wits0_profile().profile_id == "geoscape-gswits"
    assert len(wits0_catalog.load_builtin_wits0_catalog().fields) == 963
    assert localization.load_catalog(localization.AppLanguage.RU)["common.ok"] == "ОК"
    dictionary = channel_dictionary.GeoScapeChannelDictionary.load()
    assert dictionary.resolve("__missing__") is None
