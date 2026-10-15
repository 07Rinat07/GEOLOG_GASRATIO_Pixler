from pathlib import Path

import pytest

from geoworkbench.services.localization import AppLanguage
from geoworkbench.ui.daily_las_growth_result import daily_las_growth_result_text
from test_daily_las_growth_dialog import _controller


@pytest.mark.parametrize("language", list(AppLanguage))
def test_growth_receipt_uses_current_range_and_exact_project_path(language):
    dataset = _controller().session.current_dataset
    assert dataset is not None
    dataset.name = "M-1 to 5680m"
    dataset.active_index.values[-1] = 5728.2
    path = Path("result") / "M1.geologpkg"
    text = daily_las_growth_result_text(dataset, path, language)
    assert "5728.2" in text
    assert dataset.name in text
    assert str(path) in text
    assert "LAS" in text
