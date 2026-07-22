from geoworkbench.importers.paradox.progress import paradox_progress_state


def test_progress_is_stable_across_reader_phases() -> None:
    header = paradox_progress_state("header", 1, 1)
    schema = paradox_progress_state("schema", 1, 1)
    records = paradox_progress_state("records", 349, 3488)
    analysis = paradox_progress_state("analysis", 1, 1)

    assert header.overall_ratio == 0.06
    assert schema.overall_ratio == 0.14
    assert 0.19 < records.overall_ratio < 0.21
    create_start = paradox_progress_state("create", 0, 70)
    create_end = paradox_progress_state("create", 70, 70)

    assert analysis.overall_ratio == 0.86
    assert create_start.overall_ratio == 0.94
    assert create_end.overall_ratio == 1.0
    assert records.phase_number == 3


def test_progress_clamps_invalid_counts() -> None:
    assert paradox_progress_state("records", -5, 100).overall_ratio == 0.14
    assert paradox_progress_state("records", 500, 100).overall_ratio == 0.72
    assert paradox_progress_state("unknown", 1, 0).overall_ratio == 0.0
