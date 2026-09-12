from test_well_geology_update import profile

from geoworkbench.project.controller import ProjectController
from geoworkbench.services.persisted_rock_code_profile_assignment import (
    assign_persisted_rock_code_profile,
)
from geoworkbench.services.persisted_rock_code_profiles import (
    PersistedRockCodeProfileResolver,
)
from geoworkbench.storage.package_project_repository import PackageProjectRepository


def test_project_restart_retains_exact_profile_binding_and_history(tmp_path):
    controller = ProjectController(repository=PackageProjectRepository())
    source_sha256 = "a" * 64

    first_dictionary = profile("Vendor A", "Sand")
    first = assign_persisted_rock_code_profile(
        controller.session,
        source_sha256=source_sha256,
        supplier_name=first_dictionary.source,
        dictionary=first_dictionary,
    )
    second_dictionary = profile("Vendor A", "Limestone")
    second = assign_persisted_rock_code_profile(
        controller.session,
        source_sha256=source_sha256,
        supplier_name=second_dictionary.source,
        dictionary=second_dictionary,
    )

    assert first.profile.profile_sha256 != second.profile.profile_sha256
    assert controller.session.rock_code_profiles[first.profile.profile_sha256] == first.profile
    assert controller.session.rock_code_source_bindings[source_sha256] == second.binding
    assert controller.session.dirty

    path = tmp_path / "persisted-profiles.geologpkg"
    controller.save_project(path)
    assert not controller.session.dirty

    reopened = ProjectController(repository=PackageProjectRepository())
    session = reopened.open_project(path)

    assert session.rock_code_profiles == controller.session.rock_code_profiles
    assert session.rock_code_source_bindings == controller.session.rock_code_source_bindings
    assert first.profile.profile_sha256 in session.rock_code_profiles
    assert second.profile.profile_sha256 in session.rock_code_profiles

    resolved = PersistedRockCodeProfileResolver.from_session(session).require(source_sha256)
    assert resolved.binding == second.binding
    assert resolved.profile == second.profile
    assert resolved.dictionary.to_json() == second_dictionary.to_json()
    assert not session.dirty
