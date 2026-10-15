"""Regression: append a reduced daily LAS to an existing full source LAS."""

from pathlib import Path

import numpy as np

from geoworkbench.data.las_adapter import import_las_with_report
from geoworkbench.domain.models import Project
from geoworkbench.project.daily_las_growth_controller import DailyLasGrowthController
from geoworkbench.project.session import ProjectSession


_FIXTURES = Path(__file__).parent / "fixtures" / "las_sync"


def test_controller_imports_reduced_daily_las_without_dropping_prior_curves(tmp_path: Path):
    imported = import_las_with_report(_FIXTURES / "01_initial.las")
    session = ProjectSession(project=Project("partial-las", "Partial append"))
    session.add_dataset(
        imported.dataset,
        source_document=imported.source_document,
        import_report=imported.report,
        create_new_well=True,
    )
    target = session.current_dataset
    assert target is not None

    full_source = (_FIXTURES / "02_daily_append.las").read_text()
    daily_file = tmp_path / "M1_daily_reduced.las"
    head, data = full_source.split("~Ascii\n", 1)
    head = "\n".join(
        line for line in head.splitlines() if not line.strip().startswith("C1.%")
    )
    daily_file.write_text(
        head + "\n~Ascii\n"
        + "\n".join(" ".join(row.split()[:2]) for row in data.splitlines() if row.strip())
        + "\n",
        encoding="utf-8",
    )

    old_depth = target.depth.copy()
    old_c1 = target.curve_by_mnemonic("C1").values.copy()
    controller = DailyLasGrowthController(session)
    plan = controller.analyze(daily_file, target.dataset_id)
    assert plan.rows_added == 4
    assert plan.rows_skipped == 1
    assert plan.missing_curve_mnemonics == ("C1",)
    outcome = controller.apply(plan)
    assert outcome.record is not None
    assert len(target.depth) == len(old_depth) + 4
    np.testing.assert_array_equal(target.depth[:len(old_depth)], old_depth)
    np.testing.assert_array_equal(target.curve_by_mnemonic("C1").values[:len(old_c1)], old_c1)
    assert np.isnan(target.curve_by_mnemonic("C1").values[-4:]).all()
    np.testing.assert_allclose(
        target.curve_by_mnemonic("ROP").values[-4:], [15, 16, 17, 18],
    )
    assert session.dirty
    assert outcome.record.curve_mnemonics == ("ROP",)
