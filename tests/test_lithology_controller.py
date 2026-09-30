import numpy as np
import pytest

from geoworkbench.domain.models import Dataset, DatasetKind, DepthDomain
from geoworkbench.project.lithology_controller import LithologyController
from geoworkbench.project.session import ProjectSession
from geoworkbench.services.edit_history import CommandHistory


def make_controller(shared_history: CommandHistory | None = None) -> LithologyController:
    dataset = Dataset("dataset", "Well", DatasetKind.GTI, DepthDomain.MD, np.array([100.0, 200.0]))
    session = ProjectSession()
    session.add_dataset(dataset)
    session.dirty = False
    return LithologyController(session, shared_history=shared_history)


def test_lithology_controller_crud_and_adjacent_intervals() -> None:
    controller = make_controller()
    first = controller.add(100.0, 150.0, "sandstone", description="Песчаник")
    second = controller.add(150.0, 200.0, "claystone")

    assert controller.available() == (first, second)
    controller.update(
        first.interval_id,
        top_depth=100.0,
        bottom_depth=140.0,
        lithotype_id="siltstone",
        description="Алевролит",
    )
    assert first.bottom_depth == 140.0
    assert first.lithotype_id == "siltstone"
    assert controller.remove(second.interval_id) is second
    assert controller.available() == (first,)
    assert controller.session.dirty is True


def test_lithology_controller_rejects_overlap_and_out_of_range() -> None:
    controller = make_controller()
    controller.add(120.0, 160.0, "sandstone")

    with pytest.raises(ValueError, match="пересекается"):
        controller.add(150.0, 170.0, "claystone")
    with pytest.raises(ValueError, match="диапазон"):
        controller.add(90.0, 110.0, "claystone")
    with pytest.raises(ValueError, match="меньше"):
        controller.add(180.0, 170.0, "claystone")


def test_lithology_controller_saves_all_languages_atomically() -> None:
    controller = make_controller()

    interval = controller.add(
        100.0,
        150.0,
        "sandstone",
        description_i18n={"ru": "Песчаник", "kk": "Құмтас", "en": "Sandstone"},
    )

    assert interval.description_i18n == {
        "ru": "Песчаник",
        "kk": "Құмтас",
        "en": "Sandstone",
    }
    assert interval.description == "Песчаник"


def test_invalid_multilingual_update_does_not_partially_change_interval() -> None:
    controller = make_controller()
    interval = controller.add(100.0, 150.0, "sandstone", description="Песчаник")

    with pytest.raises(ValueError, match="Неподдерживаемый язык"):
        controller.update(
            interval.interval_id,
            top_depth=110.0,
            bottom_depth=140.0,
            lithotype_id="claystone",
            description_i18n={"de": "Sandstein"},
        )

    assert (interval.top_depth, interval.bottom_depth) == (100.0, 150.0)
    assert interval.lithotype_id == "sandstone"
    assert interval.description == "Песчаник"


def test_lithology_shared_history_supports_chronological_add_update_remove() -> None:
    history = CommandHistory()
    controller = make_controller(history)

    interval = controller.add(
        100.0,
        150.0,
        "sandstone",
        description_i18n={"ru": "Песчаник", "kk": "Құмтас", "en": "Sandstone"},
        source_language="ru",
    )
    controller.update(
        interval.interval_id,
        top_depth=105.0,
        bottom_depth=145.0,
        lithotype_id="siltstone",
        description_i18n={"ru": "Алевролит", "kk": "Алевролит", "en": "Siltstone"},
        source_language="ru",
    )
    controller.remove(interval.interval_id)

    assert controller.available() == ()
    assert controller.can_undo is True

    controller.undo()
    restored = controller.get(interval.interval_id)
    assert restored is interval
    assert (restored.top_depth, restored.bottom_depth) == (105.0, 145.0)
    assert restored.lithotype_id == "siltstone"

    controller.undo()
    assert (interval.top_depth, interval.bottom_depth) == (100.0, 150.0)
    assert interval.lithotype_id == "sandstone"
    assert interval.description_i18n["en"] == "Sandstone"

    controller.undo()
    assert controller.available() == ()
    assert controller.can_redo is True

    controller.redo()
    assert controller.get(interval.interval_id) is interval
    controller.redo()
    assert interval.lithotype_id == "siltstone"
    controller.redo()
    assert controller.available() == ()


def test_lithology_local_undo_is_domain_safe_with_shared_history() -> None:
    history = CommandHistory()
    controller = make_controller(history)
    controller.add(100.0, 150.0, "sandstone")

    class OtherCommand:
        description = "other"
        history_domain = "other"

        def execute(self) -> None:
            return None

        def undo(self) -> None:
            return None

    history.execute(OtherCommand())

    assert controller.can_undo is False
    with pytest.raises(RuntimeError, match="литологии"):
        controller.undo()


def test_lithology_undo_fails_closed_after_external_interval_change() -> None:
    controller = make_controller()
    interval = controller.add(100.0, 150.0, "sandstone")
    interval.bottom_depth = 149.0

    with pytest.raises(RuntimeError, match="вне истории"):
        controller.undo()

    assert controller.can_undo is True


def test_lithology_undo_restores_translation_tracking_sidecars() -> None:
    controller = make_controller()
    well = controller.session.current_well
    assert well is not None

    interval = controller.add(
        100.0,
        150.0,
        "sandstone",
        description_i18n={"ru": "Песчаник", "kk": "Құмтас", "en": "Sandstone"},
        source_language="ru",
    )
    after_revisions = dict(well.language_revisions)
    assert well.authored_field_source_languages[
        f"lithology/{interval.interval_id}/description"
    ] == "ru"

    controller.undo()

    assert controller.available() == ()
    assert f"lithology/{interval.interval_id}/description" not in (
        well.authored_field_source_languages
    )

    controller.redo()

    assert controller.get(interval.interval_id) is interval
    assert well.language_revisions == after_revisions
    assert well.authored_field_source_languages[
        f"lithology/{interval.interval_id}/description"
    ] == "ru"
