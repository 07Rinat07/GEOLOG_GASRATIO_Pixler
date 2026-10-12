import numpy as np
import pytest
from PySide6.QtCore import QSettings

from geoworkbench.domain.models import Well
from geoworkbench.services.localization import AppLanguage
from geoworkbench.services.wits0_acquisition import Wits0AcquisitionRuntime
import geoworkbench.ui.wits0_live_view as live
from test_wits0_acquisition import _frame, _time_commit


@pytest.mark.parametrize("language", list(AppLanguage))
def test_real_manual_panel_range_survives_saved_form_and_runtime_rebind(qapp, tmp_path, monkeypatch, language):
    _profile, frames, commit = _time_commit(
        _frame(2, 1, "0208123.4", "021011.2"),
        _frame(2, 2, "0208123.6", "021012.0"),
    )
    runtime = Wits0AcquisitionRuntime(Well("range-well", "Range"), commit, session_id="range-session")
    runtime.submit_frame(frames[0])
    runtime.flush()
    before = {key: curve.values.copy() for key, curve in runtime.controller.dataset.curves.items()}
    settings_path = str(tmp_path / "forms.ini")
    monkeypatch.setattr(live, "QSettings", lambda: QSettings(settings_path, QSettings.Format.IniFormat))
    widget = live.Wits0LiveViewWidget(language=language)
    reopened = None
    try:
        widget.bind_runtime(runtime)
        widget._sync_panel_controls_from_dashboard()
        assert widget.panel_scale_combo.count() > 0
        scale_key = str(widget.panel_scale_combo.currentData())
        widget.panel_x_auto_check.setChecked(False)
        widget.panel_x_min_spin.setValue(10.0)
        widget.panel_x_max_spin.setValue(200.0)
        widget.panel_x_apply_button.click()
        expected = ((scale_key, 10.0, 200.0),)
        assert widget.dashboard.panel_x_ranges() == expected
        assert widget.save_form_button.isEnabled()
        widget.save_form_button.click()
        widget.settings.sync()
        widget.bind_runtime(None)
        widget.bind_runtime(runtime)
        assert widget.dashboard.panel_x_ranges() == expected
        reopened = live.Wits0LiveViewWidget(language=language)
        reopened.bind_runtime(runtime)
        assert reopened.dashboard.panel_x_ranges() == expected
        runtime.submit_frame(frames[1])
        runtime.flush()
        reopened.refresh()
        assert reopened.dashboard.panel_x_ranges() == expected
        for key, values in before.items():
            np.testing.assert_array_equal(runtime.controller.dataset.curves[key].values[:len(values)], values)
    finally:
        for current in (widget, reopened):
            if current is not None:
                current.close()
                current.deleteLater()
        qapp.processEvents()
