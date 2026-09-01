from __future__ import annotations

from pathlib import Path
import shutil
from zipfile import ZipFile

import fitz
import numpy as np
import pytest

from geoworkbench.data.las_adapter import import_las_with_report
from geoworkbench.domain.localized_content import localized_text
from geoworkbench.domain.models import (
    MasterlogColumnTemplate,
    MasterlogTemplate,
    Project,
)
from geoworkbench.printing.masterlog_output import MasterlogOutputSettings
from geoworkbench.printing.masterlog_renderer import export_masterlog_pdf
from geoworkbench.project.annotation_controller import DepthAnnotationController
from geoworkbench.project.annotation_schema import AnnotationAnchor, AnnotationKind
from geoworkbench.project.controller import ProjectController
from geoworkbench.project.cuttings_controller import CuttingsController
from geoworkbench.project.daily_las_growth_controller import DailyLasGrowthController
from geoworkbench.project.lithology_controller import LithologyController
from geoworkbench.project.session import ProjectSession
from geoworkbench.project.stratigraphy_controller import StratigraphyController
from geoworkbench.services.daily_las_growth import DailyLasGrowthError
from geoworkbench.services.local_las_folder import LocalLasFolderProvider
from geoworkbench.services.localization import AppLanguage
from geoworkbench.storage.package_project_repository import (
    PackageProjectRepository,
    ProjectPackageError,
)


FIXTURES = Path(__file__).parent / "fixtures" / "las_sync"


def _new_session() -> tuple[ProjectSession, str]:
    imported = import_las_with_report(FIXTURES / "01_initial.las")
    session = ProjectSession(project=Project("project-test-101", "TEST-101 multilingual"))
    session.add_dataset(
        imported.dataset,
        source_document=imported.source_document,
        import_report=imported.report,
        create_new_well=True,
    )
    return session, imported.dataset.dataset_id


def _fill_all_languages(session: ProjectSession) -> dict[str, str]:
    lithology = LithologyController(session)
    lith = lithology.add(
        1000.0,
        1001.0,
        "sandstone",
        description="Песчаник мелкозернистый",
        content_language="ru",
    )
    lithology.update(
        lith.interval_id,
        top_depth=1000.0,
        bottom_depth=1001.0,
        lithotype_id="sandstone",
        description="Ұсақ түйірлі құмтас",
        content_language="kk",
    )
    lithology.update(
        lith.interval_id,
        top_depth=1000.0,
        bottom_depth=1001.0,
        lithotype_id="sandstone",
        description="Fine-grained sandstone",
        content_language="en",
    )

    cuttings = CuttingsController(session)
    sample = cuttings.set_description(
        1001.0,
        1002.0,
        "Шлам песчаный, следы нефти",
        language="ru",
    )
    cuttings.set_description(
        1001.0,
        1002.0,
        "Құмды шлам, мұнай іздері",
        language="kk",
    )
    cuttings.set_description(
        1001.0,
        1002.0,
        "Sandy cuttings with oil traces",
        language="en",
    )
    for language, lba, conclusion in (
        ("ru", "Жёлтая флуоресценция", "Коллектор вероятен"),
        ("kk", "Сары флуоресценция", "Коллектор болуы ықтимал"),
        ("en", "Yellow fluorescence", "Reservoir is probable"),
    ):
        cuttings.set_analysis(
            1001.0,
            1002.0,
            calcite_percent=35.0,
            dolomite_percent=10.0,
            lba_group=2,
            lba_intensity=3,
            lba_description=lba,
            analysis_interpretation=conclusion,
            content_language=language,
        )

    stratigraphy = StratigraphyController(session)
    strat = stratigraphy.add(
        1000.0,
        1002.0,
        "K1",
        name="Меловая система",
        description="Нижний мел",
        content_language="ru",
    )
    stratigraphy.update(
        strat.interval_id,
        top_depth=1000.0,
        bottom_depth=1002.0,
        code="K1",
        name="Бор жүйесі",
        description="Төменгі бор",
        content_language="kk",
    )
    stratigraphy.update(
        strat.interval_id,
        top_depth=1000.0,
        bottom_depth=1002.0,
        code="K1",
        name="Cretaceous system",
        description="Lower Cretaceous",
        content_language="en",
    )

    annotations = DepthAnnotationController(session)
    note = annotations.add_annotation(
        kind=AnnotationKind.COMMENT,
        anchor=AnnotationAnchor.DEPTH,
        depth=1001.5,
        text="Текстовая заметка",
        content_language="ru",
    )
    annotations.update_annotation(
        note.annotation_id,
        text="Мәтіндік ескертпе",
        content_language="kk",
    )
    annotations.update_annotation(
        note.annotation_id,
        text="Text note",
        content_language="en",
    )
    return {
        "lithology": lith.interval_id,
        "sample": sample.sample_id,
        "stratigraphy": strat.interval_id,
        "annotation": note.annotation_id,
    }


def _assert_languages(session: ProjectSession, ids: dict[str, str]) -> None:
    assert session.current_well is not None
    well = session.current_well
    lith = next(item for item in well.lithology if item.interval_id == ids["lithology"])
    sample = next(item for item in well.cuttings if item.sample_id == ids["sample"])
    strat = next(item for item in well.stratigraphy if item.interval_id == ids["stratigraphy"])
    note = DepthAnnotationController(session).get(ids["annotation"])

    assert localized_text(lith.description_i18n, "ru") == "Песчаник мелкозернистый"
    assert localized_text(lith.description_i18n, "kk") == "Ұсақ түйірлі құмтас"
    assert localized_text(lith.description_i18n, "en") == "Fine-grained sandstone"
    assert localized_text(sample.description_i18n, "ru") == "Шлам песчаный, следы нефти"
    assert localized_text(sample.description_i18n, "kk") == "Құмды шлам, мұнай іздері"
    assert localized_text(sample.description_i18n, "en") == "Sandy cuttings with oil traces"
    assert localized_text(sample.lba_description_i18n, "en") == "Yellow fluorescence"
    assert localized_text(sample.analysis_interpretation_i18n, "kk") == "Коллектор болуы ықтимал"
    assert localized_text(strat.name_i18n, "ru") == "Меловая система"
    assert localized_text(strat.name_i18n, "kk") == "Бор жүйесі"
    assert localized_text(strat.name_i18n, "en") == "Cretaceous system"
    assert localized_text(note.text_i18n, "ru") == "Текстовая заметка"
    assert localized_text(note.text_i18n, "kk") == "Мәтіндік ескертпе"
    assert localized_text(note.text_i18n, "en") == "Text note"
    assert well.language_revisions == {"ru": 5, "kk": 5, "en": 5}


def _print_template() -> MasterlogTemplate:
    return MasterlogTemplate(
        "multilingual-test",
        "Multilingual test",
        page_format="roll",
        header_height_mm=10.0,
        columns=[
            MasterlogColumnTemplate("depth", "Depth", "depth", 18.0),
            MasterlogColumnTemplate("lith", "Lithology", "text", 45.0),
            MasterlogColumnTemplate("cut", "Cuttings", "cuttings_description", 55.0),
            MasterlogColumnTemplate("analysis", "Analysis", "analysis_interpretation", 55.0),
            MasterlogColumnTemplate("calc", "Calcimetry", "calcimetry", 35.0),
            MasterlogColumnTemplate("lba", "LBA", "lba", 35.0),
        ],
        properties={"body_height_mm": 220.0},
    )


def test_complete_multilingual_local_folder_append_and_transfer_workflow(
    tmp_path: Path, qapp
) -> None:
    session, dataset_id = _new_session()
    ids = _fill_all_languages(session)
    package = tmp_path / "TEST-101.geologpkg"
    ProjectController(session=session).save_project(package)

    reopened_controller = ProjectController()
    reopened = reopened_controller.open_project(package)
    _assert_languages(reopened, ids)
    assert reopened.current_dataset is not None
    assert np.array_equal(
        reopened.current_dataset.depth,
        np.asarray([1000.0, 1000.5, 1001.0, 1001.5, 1002.0]),
    )

    provider = LocalLasFolderProvider(FIXTURES)
    candidates = {item.relative_path: item for item in provider.discover()}
    daily = provider.verify(candidates["02_daily_append.las"])
    growth = DailyLasGrowthController(reopened)
    plan = growth.analyze(
        daily.path,
        dataset_id,
        provider_kind=provider.provider_kind,
        provider_location=f"{FIXTURES}::{daily.relative_path}",
    )
    outcome = growth.apply(plan)
    assert outcome.record is not None
    assert plan.rows_added == 4
    assert plan.rows_skipped == 1
    assert reopened.current_dataset is not None
    assert reopened.current_dataset.depth[-1] == pytest.approx(1004.0)
    assert len(reopened.current_dataset.source_revisions) == 2
    assert len(reopened.source_documents) == 2
    _assert_languages(reopened, ids)

    reopened_controller.save_project()
    after_append = ProjectController().open_project(package)
    _assert_languages(after_append, ids)
    assert after_append.current_dataset is not None
    assert len(after_append.current_dataset.append_history) == 1
    depth_before_duplicate = after_append.current_dataset.depth.copy()

    duplicate_growth = DailyLasGrowthController(after_append)
    duplicate_plan = duplicate_growth.analyze(
        daily.path,
        dataset_id,
        provider_kind=provider.provider_kind,
        provider_location=f"{FIXTURES}::{daily.relative_path}",
    )
    duplicate_outcome = duplicate_growth.apply(duplicate_plan)
    assert duplicate_plan.duplicate_source is True
    assert duplicate_outcome.record is None
    assert np.array_equal(after_append.current_dataset.depth, depth_before_duplicate)
    assert len(after_append.current_dataset.append_history) == 1

    conflicting = provider.verify(candidates["03_conflict.las"])
    conflict_depth = after_append.current_dataset.depth.copy()
    with pytest.raises(DailyLasGrowthError, match="Конфликт"):
        DailyLasGrowthController(after_append).analyze(
            conflicting.path,
            dataset_id,
            provider_kind=provider.provider_kind,
            provider_location=f"{FIXTURES}::{conflicting.relative_path}",
        )
    assert np.array_equal(after_append.current_dataset.depth, conflict_depth)

    for language in AppLanguage:
        target = tmp_path / f"TEST-101-{language.value}.pdf"
        export_masterlog_pdf(
            _print_template(),
            after_append,
            target,
            settings=MasterlogOutputSettings(1000.0, 1004.0, language),
        )
        with fitz.open(target) as document:
            assert document.page_count >= 1

    transfer_dir = tmp_path / "other-computer"
    transfer_dir.mkdir()
    transferred = transfer_dir / package.name
    shutil.copy2(package, transferred)
    transferred_session = ProjectController().open_project(transferred)
    _assert_languages(transferred_session, ids)
    assert transferred_session.current_dataset is not None
    assert transferred_session.current_dataset.depth[-1] == pytest.approx(1004.0)
    assert len(transferred_session.current_dataset.source_revisions) == 2


def test_local_las_folder_rejects_changed_candidate(tmp_path: Path) -> None:
    source = tmp_path / "daily.las"
    shutil.copy2(FIXTURES / "02_daily_append.las", source)
    provider = LocalLasFolderProvider(tmp_path)
    candidate = provider.discover()[0]
    source.write_text(source.read_text(encoding="utf-8") + "\n", encoding="utf-8")

    with pytest.raises(RuntimeError, match="изменился"):
        provider.verify(candidate)


def test_daily_append_rejects_file_changed_after_preview(tmp_path: Path) -> None:
    session, dataset_id = _new_session()
    source = tmp_path / "daily.las"
    shutil.copy2(FIXTURES / "02_daily_append.las", source)
    controller = DailyLasGrowthController(session)
    plan = controller.analyze(source, dataset_id)
    assert session.current_dataset is not None
    original_depth = session.current_dataset.depth.copy()

    source.write_text(source.read_text(encoding="utf-8") + "\n", encoding="utf-8")

    with pytest.raises(DailyLasGrowthError, match="изменился после анализа"):
        controller.apply(plan)
    assert np.array_equal(session.current_dataset.depth, original_depth)
    assert session.current_dataset.append_history == []
    assert session.current_dataset.source_revisions == []
    with pytest.raises(RuntimeError, match="Сначала повторно проанализируйте"):
        controller.apply(plan)


def test_geologpkg_rejects_unsafe_archive_member(tmp_path: Path) -> None:
    package = tmp_path / "unsafe.geologpkg"
    with ZipFile(package, "w") as archive:
        archive.writestr("manifest.json", "{}")
        archive.writestr("project.geolog.json", "{}")
        archive.writestr("../outside.txt", "must not be extracted")

    with pytest.raises(ProjectPackageError, match="небезопасный путь"):
        PackageProjectRepository().load(package)
