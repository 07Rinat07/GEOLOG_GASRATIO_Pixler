from hashlib import sha256
import json

import pytest

from geoworkbench.domain.models import (
    MasterlogColumnTemplate,
    MasterlogCurveStyle,
    MasterlogHeaderElement,
    MasterlogTemplate,
)
from geoworkbench.printing.image_assets import ImageAsset
from geoworkbench.printing.masterlog_package import (
    MasterlogPackageError,
    export_masterlog_package,
    load_masterlog_package,
)
from geoworkbench.project.masterlog_template_controller import MasterlogTemplateController
from geoworkbench.project.session import ProjectSession


PNG = b"\x89PNG\r\n\x1a\nportable-logo"
SVG = b'<svg xmlns="http://www.w3.org/2000/svg" width="20" height="10"><rect width="20" height="10" fill="#f00"/></svg>'


def make_template_and_session() -> tuple[MasterlogTemplate, ProjectSession]:
    digest = sha256(PNG).hexdigest()
    asset = ImageAsset(f"sha256:{digest}", "logo.png", "image/png", PNG)
    template = MasterlogTemplate(
        "standard",
        "Portable",
        page_format="A3",
        header_elements=[
            MasterlogHeaderElement(
                "logo", "image", 5.0, 5.0, 30.0, 20.0, {"asset_ref": asset.asset_id}
            ),
            MasterlogHeaderElement(
                "legend",
                "lithology_legend",
                40.0,
                5.0,
                120.0,
                20.0,
                {"scope": "used", "columns": 4, "show_code": True},
            ),
        ],
        columns=[
            MasterlogColumnTemplate("depth", "Depth", "depth", 25.0),
            MasterlogColumnTemplate(
                "gas",
                "Gas",
                "curves",
                40.0,
                ["TG"],
                curve_styles={"TG": MasterlogCurveStyle("#ff0000", 2.5, "dash", 1.0, 1000.0)},
                grid_x=True,
                grid_y=True,
                grid_major_divisions=4,
                grid_minor_divisions=8,
                grid_alpha=0.35,
            ),
        ],
        properties={"orientation": "landscape"},
        version=7,
    )
    return template, ProjectSession(image_assets={asset.asset_id: asset})


def test_masterlog_package_round_trip_and_independent_install(tmp_path) -> None:
    template, session = make_template_and_session()
    unused_payload = b"\x89PNG\r\n\x1a\nunused"
    unused_digest = sha256(unused_payload).hexdigest()
    unused = ImageAsset(f"sha256:{unused_digest}", "unused.png", "image/png", unused_payload)
    session.image_assets[unused.asset_id] = unused
    target = tmp_path / "portable.json"

    export_masterlog_package(template, session, target)
    package = load_masterlog_package(target)
    destination = ProjectSession()
    controller = MasterlogTemplateController(destination)
    imported = controller.import_template(
        package.template, package.image_assets, "Imported portable"
    )

    assert package.template.header_elements[0].properties["asset_ref"] in package.image_assets
    assert unused.asset_id not in package.image_assets
    assert imported.template_id != template.template_id
    assert imported.name == "Imported portable"
    assert imported.version == 1
    assert imported.columns[1].curve_styles["TG"].line_style == "dash"
    assert imported.columns[1].curve_styles["TG"].x_max == 1000.0
    assert imported.columns[1].grid_x is True
    assert imported.columns[1].grid_y is True
    assert imported.columns[1].grid_major_divisions == 4
    assert imported.columns[1].grid_minor_divisions == 8
    assert imported.columns[1].grid_alpha == 0.35
    assert imported.header_elements[1].element_type == "lithology_legend"
    assert imported.header_elements[1].properties["scope"] == "used"
    assert destination.image_assets == package.image_assets
    with pytest.raises(ValueError):
        controller.import_template(package.template, package.image_assets, "Imported portable")


def test_masterlog_package_rejects_missing_or_tampered_asset(tmp_path) -> None:
    template, session = make_template_and_session()
    target = tmp_path / "portable.json"
    export_masterlog_package(template, session, target)
    payload = json.loads(target.read_text(encoding="utf-8"))
    asset_data = next(iter(payload["image_assets"].values()))
    asset_data["payload_base64"] = "invalid!"
    target.write_text(json.dumps(payload), encoding="utf-8")

    with pytest.raises(MasterlogPackageError):
        load_masterlog_package(target)

    session.image_assets.clear()
    with pytest.raises(MasterlogPackageError):
        export_masterlog_package(template, session, tmp_path / "missing.json")


def test_masterlog_package_does_not_overwrite_without_permission(tmp_path) -> None:
    template, session = make_template_and_session()
    target = tmp_path / "portable.json"
    export_masterlog_package(template, session, target)

    with pytest.raises(FileExistsError):
        export_masterlog_package(template, session, target)


def test_masterlog_package_round_trips_safe_svg_and_reads_v1_png(tmp_path) -> None:
    template, session = make_template_and_session()
    digest = sha256(SVG).hexdigest()
    svg = ImageAsset(f"sha256:{digest}", "logo.svg", "image/svg+xml", SVG)
    template.header_elements[0].properties["asset_ref"] = svg.asset_id
    session.image_assets = {svg.asset_id: svg}
    target = tmp_path / "svg-package.json"

    export_masterlog_package(template, session, target)
    package = load_masterlog_package(target)
    assert package.image_assets[svg.asset_id] == svg

    legacy_template, legacy_session = make_template_and_session()
    legacy = tmp_path / "legacy.json"
    export_masterlog_package(legacy_template, legacy_session, legacy)
    payload = json.loads(legacy.read_text(encoding="utf-8"))
    payload["package_version"] = 1
    legacy.write_text(json.dumps(payload), encoding="utf-8")
    assert load_masterlog_package(legacy).template.name == "Portable"
